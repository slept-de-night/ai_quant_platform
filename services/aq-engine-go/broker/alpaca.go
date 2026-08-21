package broker

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"sync"
	"time"

	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

type AlpacaAdapter struct {
	name        string
	apiKey      string
	secretKey   string
	baseURL     string
	environment Environment
	client      *http.Client

	mu        sync.Mutex
	connected bool
	ready     bool
	probeMsg  string
	lastProbe time.Time
}

func NewAlpacaPaperClient(apiKey, secretKey string) *AlpacaAdapter {
	return NewAlpacaAdapter("alpaca-paper", apiKey, secretKey, true)
}

func NewAlpacaAdapter(name, apiKey, secretKey string, isPaper bool) *AlpacaAdapter {
	baseURL := "https://paper-api.alpaca.markets"
	if !isPaper {
		baseURL = "https://api.alpaca.markets"
	}
	environment := EnvPaper
	if !isPaper {
		environment = EnvLive
	}
	if name == "" {
		name = "alpaca-paper"
	}
	return &AlpacaAdapter{
		name:        name,
		apiKey:      apiKey,
		secretKey:   secretKey,
		baseURL:     baseURL,
		environment: environment,
		client:      &http.Client{Timeout: 10 * time.Second},
	}
}

func (c *AlpacaAdapter) SetBaseURL(u string) {
	c.baseURL = u
}

func (c *AlpacaAdapter) Name() string {
	return c.name
}

func (c *AlpacaAdapter) Kind() BrokerKind {
	return BrokerKindAlpaca
}

// Environment reports the explicitly configured execution environment. It is
// fixed at construction from the isPaper flag and MUST NOT be inferred from
// the HTTP URL, so test servers that override the URL never relabel a venue.
func (c *AlpacaAdapter) Environment() Environment {
	return c.environment
}

func (c *AlpacaAdapter) IsConfigured() bool {
	return c.apiKey != "" && c.secretKey != ""
}

// doRequest is the centralized, sanitized HTTP execution engine for Alpaca REST endpoints.
// It enforces timeouts, authentication headers, and safe error masking (no leaked credentials).
func (c *AlpacaAdapter) doRequest(ctx context.Context, method, endpoint string, payload interface{}) ([]byte, int, error) {
	var bodyReader io.Reader
	if payload != nil {
		reqBytes, err := json.Marshal(payload)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to encode request payload: %w", err)
		}
		bodyReader = bytes.NewBuffer(reqBytes)
	}

	fullURL := c.baseURL + endpoint
	req, err := http.NewRequestWithContext(ctx, method, fullURL, bodyReader)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to create http request: %w", err)
	}

	req.Header.Set("APCA-API-KEY-ID", c.apiKey)
	req.Header.Set("APCA-API-SECRET-KEY", c.secretKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		// Clean error without exposing secret keys
		return nil, 0, fmt.Errorf("alpaca request to %s failed: %w", endpoint, err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode >= 400 {
		return respBody, resp.StatusCode, fmt.Errorf("alpaca error (%d) on %s: %s", resp.StatusCode, endpoint, string(respBody))
	}

	return respBody, resp.StatusCode, nil
}

type alpacaOrderRequest struct {
	Symbol        string `json:"symbol"`
	Qty           int    `json:"qty"`
	Side          string `json:"side"`
	Type          string `json:"type"`
	TimeInForce   string `json:"time_in_force"`
	ClientOrderID string `json:"client_order_id"`
}

type alpacaOrderResponse struct {
	ID             string  `json:"id"`
	ClientOrderID  string  `json:"client_order_id"`
	CreatedAt      string  `json:"created_at"`
	UpdatedAt      string  `json:"updated_at"`
	SubmittedAt    string  `json:"submitted_at"`
	FilledAt       *string `json:"filled_at"`
	Symbol         string  `json:"symbol"`
	Qty            string  `json:"qty"`
	FilledQty      string  `json:"filled_qty"`
	Type           string  `json:"type"`
	Side           string  `json:"side"`
	TimeInForce    string  `json:"time_in_force"`
	LimitPrice     *string `json:"limit_price"`
	FilledAvgPrice *string `json:"filled_avg_price"`
	Status         string  `json:"status"`
}

func parseAlpacaOrder(res alpacaOrderResponse) (BrokerOrder, error) {
	qtyInt, err := strconv.Atoi(res.Qty)
	if err != nil && res.Qty != "" {
		return BrokerOrder{}, fmt.Errorf("failed to parse order qty '%s': %w", res.Qty, err)
	}
	filledQtyInt, err := strconv.Atoi(res.FilledQty)
	if err != nil && res.FilledQty != "" {
		return BrokerOrder{}, fmt.Errorf("failed to parse filled qty '%s': %w", res.FilledQty, err)
	}

	var avgFillPrice float64
	if res.FilledAvgPrice != nil && *res.FilledAvgPrice != "" {
		p, err := strconv.ParseFloat(*res.FilledAvgPrice, 64)
		if err != nil {
			return BrokerOrder{}, fmt.Errorf("failed to parse filled avg price '%s': %w", *res.FilledAvgPrice, err)
		}
		avgFillPrice = p
	}

	var limitPrice float64
	if res.LimitPrice != nil && *res.LimitPrice != "" {
		p, err := strconv.ParseFloat(*res.LimitPrice, 64)
		if err != nil {
			return BrokerOrder{}, fmt.Errorf("failed to parse limit price '%s': %w", *res.LimitPrice, err)
		}
		limitPrice = p
	}

	createdAt, err := time.Parse(time.RFC3339Nano, res.CreatedAt)
	if err != nil {
		return BrokerOrder{}, fmt.Errorf("failed to parse created_at '%s': %w", res.CreatedAt, err)
	}
	updatedAt, err := time.Parse(time.RFC3339Nano, res.UpdatedAt)
	if err != nil {
		return BrokerOrder{}, fmt.Errorf("failed to parse updated_at '%s': %w", res.UpdatedAt, err)
	}

	return BrokerOrder{
		ID:               res.ID,
		BrokerOrderID:    res.ID,
		ClientOrderID:    res.ClientOrderID,
		Symbol:           res.Symbol,
		Side:             res.Side,
		Qty:              qtyInt,
		RequestedQty:     float64(qtyInt),
		FilledQty:        filledQtyInt,
		FilledQtyFloat:   float64(filledQtyInt),
		Status:           NormalizeBrokerStatus(res.Status),
		RawStatus:        res.Status,
		LimitPrice:       limitPrice,
		AvgPrice:         avgFillPrice,
		AverageFillPrice: avgFillPrice,
		CreatedAt:        createdAt,
		UpdatedAt:        updatedAt,
	}, nil
}

func (c *AlpacaAdapter) SubmitOrder(order *models.OrderIntent) (*BrokerOrder, error) {
	if !c.IsConfigured() {
		return nil, fmt.Errorf("broker not configured: alpaca credentials missing")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	payload := alpacaOrderRequest{
		Symbol:        order.Symbol,
		Qty:           order.Qty,
		Side:          string(order.Side),
		Type:          "market",
		TimeInForce:   "day",
		ClientOrderID: order.ClientOrderID,
	}

	bodyBytes, _, err := c.doRequest(ctx, "POST", "/v2/orders", payload)
	if err != nil {
		return nil, err
	}

	var res alpacaOrderResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, fmt.Errorf("failed to parse alpaca order response: %w", err)
	}

	bo, err := parseAlpacaOrder(res)
	if err != nil {
		return nil, err
	}
	if bo.LimitPrice == 0 {
		bo.LimitPrice = order.ReferencePrice
	}
	return &bo, nil
}

func (c *AlpacaAdapter) CancelOrder(clientOrderID string) error {
	if !c.IsConfigured() {
		return fmt.Errorf("broker not configured: alpaca credentials missing")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	endpoint := fmt.Sprintf("/v2/orders:by_client_order_id?client_order_id=%s", url.QueryEscape(clientOrderID))
	_, _, err := c.doRequest(ctx, "DELETE", endpoint, nil)
	return err
}

func (c *AlpacaAdapter) GetOrder(clientOrderID string) (*BrokerOrder, error) {
	if !c.IsConfigured() {
		return nil, fmt.Errorf("broker not configured: alpaca credentials missing")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	endpoint := fmt.Sprintf("/v2/orders:by_client_order_id?client_order_id=%s", url.QueryEscape(clientOrderID))
	bodyBytes, statusCode, err := c.doRequest(ctx, "GET", endpoint, nil)
	if err != nil {
		if statusCode == http.StatusNotFound {
			return nil, ErrOrderNotFound
		}
		return nil, err
	}

	var res alpacaOrderResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, fmt.Errorf("failed to parse alpaca order response: %w", err)
	}

	bo, err := parseAlpacaOrder(res)
	if err != nil {
		return nil, err
	}
	return &bo, nil
}

func (c *AlpacaAdapter) GetOrderByBrokerID(brokerOrderID string) (*BrokerOrder, error) {
	if !c.IsConfigured() {
		return nil, fmt.Errorf("broker not configured")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	endpoint := fmt.Sprintf("/v2/orders/%s", url.PathEscape(brokerOrderID))
	bodyBytes, _, err := c.doRequest(ctx, "GET", endpoint, nil)
	if err != nil {
		return nil, err
	}

	var res alpacaOrderResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, fmt.Errorf("failed to parse alpaca order response: %w", err)
	}

	bo, err := parseAlpacaOrder(res)
	if err != nil {
		return nil, err
	}
	return &bo, nil
}

func (c *AlpacaAdapter) ListOrders() ([]BrokerOrder, error) {
	if !c.IsConfigured() {
		return nil, fmt.Errorf("broker not configured: alpaca credentials missing")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	var allOrders []BrokerOrder
	seen := make(map[string]bool)
	limit := 500
	maxPages := 10
	var untilParam string

	for page := 0; page < maxPages; page++ {
		endpoint := fmt.Sprintf("/v2/orders?status=all&limit=%d&direction=desc", limit)
		if untilParam != "" {
			endpoint += fmt.Sprintf("&until=%s", url.QueryEscape(untilParam))
		}

		bodyBytes, _, err := c.doRequest(ctx, "GET", endpoint, nil)
		if err != nil {
			return nil, err
		}

		var resList []alpacaOrderResponse
		if err := json.Unmarshal(bodyBytes, &resList); err != nil {
			return nil, fmt.Errorf("failed to parse alpaca order list: %w", err)
		}

		if len(resList) == 0 {
			break
		}

		for _, res := range resList {
			if res.ID != "" && seen[res.ID] {
				continue
			}
			bo, err := parseAlpacaOrder(res)
			if err != nil {
				return nil, err
			}
			if res.ID != "" {
				seen[res.ID] = true
			}
			allOrders = append(allOrders, bo)
		}

		if len(resList) < limit {
			break
		}

		oldestCreatedAt := resList[len(resList)-1].CreatedAt
		if oldestCreatedAt == "" || oldestCreatedAt == untilParam {
			break
		}
		untilParam = oldestCreatedAt
	}

	return allOrders, nil
}

type alpacaPositionResponse struct {
	Symbol       string `json:"symbol"`
	Qty          string `json:"qty"`
	MarketValue  string `json:"market_value"`
	CostBasis    string `json:"cost_basis"`
	CurrentPrice string `json:"current_price"`
}

func (c *AlpacaAdapter) ListPositions() ([]BrokerPosition, error) {
	if !c.IsConfigured() {
		return nil, fmt.Errorf("broker not configured: alpaca credentials missing")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	bodyBytes, _, err := c.doRequest(ctx, "GET", "/v2/positions", nil)
	if err != nil {
		return nil, err
	}

	var resList []alpacaPositionResponse
	if err := json.Unmarshal(bodyBytes, &resList); err != nil {
		return nil, fmt.Errorf("failed to parse alpaca positions: %w", err)
	}

	positions := make([]BrokerPosition, len(resList))
	for i, pos := range resList {
		qty, err := strconv.ParseFloat(pos.Qty, 64)
		if err != nil && pos.Qty != "" {
			return nil, fmt.Errorf("failed to parse position qty '%s': %w", pos.Qty, err)
		}
		mv, err := strconv.ParseFloat(pos.MarketValue, 64)
		if err != nil && pos.MarketValue != "" {
			return nil, fmt.Errorf("failed to parse position market value '%s': %w", pos.MarketValue, err)
		}
		cb, err := strconv.ParseFloat(pos.CostBasis, 64)
		if err != nil && pos.CostBasis != "" {
			return nil, fmt.Errorf("failed to parse position cost basis '%s': %w", pos.CostBasis, err)
		}
		positions[i] = BrokerPosition{
			Symbol:      pos.Symbol,
			Qty:         qty,
			MarketValue: mv,
			CostBasis:   cb,
		}
	}
	return positions, nil
}

type alpacaAccountResponse struct {
	Cash        string `json:"cash"`
	Equity      string `json:"equity"`
	BuyingPower string `json:"buying_power"`
	Currency    string `json:"currency"`
	Status      string `json:"status"`
}

func (c *AlpacaAdapter) GetAccountState() (*AccountState, error) {
	if !c.IsConfigured() {
		return nil, fmt.Errorf("broker not configured: alpaca credentials missing")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	bodyBytes, _, err := c.doRequest(ctx, "GET", "/v2/account", nil)
	if err != nil {
		return nil, err
	}

	var res alpacaAccountResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, fmt.Errorf("failed to parse alpaca account: %w", err)
	}

	cash, err := strconv.ParseFloat(res.Cash, 64)
	if err != nil && res.Cash != "" {
		return nil, fmt.Errorf("failed to parse account cash '%s': %w", res.Cash, err)
	}
	equity, err := strconv.ParseFloat(res.Equity, 64)
	if err != nil && res.Equity != "" {
		return nil, fmt.Errorf("failed to parse account equity '%s': %w", res.Equity, err)
	}
	buyingPower, err := strconv.ParseFloat(res.BuyingPower, 64)
	if err != nil && res.BuyingPower != "" {
		return nil, fmt.Errorf("failed to parse account buying power '%s': %w", res.BuyingPower, err)
	}

	return &AccountState{
		Cash:        cash,
		Equity:      equity,
		BuyingPower: buyingPower,
		Currency:    res.Currency,
	}, nil
}

func (c *AlpacaAdapter) GetHealth() Health {
	c.mu.Lock()
	defer c.mu.Unlock()

	configured := c.IsConfigured()
	if !configured {
		return Health{
			Configured:    false,
			Ready:         false,
			Connected:     false,
			Broker:        BrokerKindAlpaca,
			Name:          c.name,
			Environment:   c.Environment(),
			Message:       "Alpaca adapter unconfigured (credentials missing); not ready for broker execution",
			LastCheckedAt: c.lastProbe,
		}
	}

	msg := "Alpaca configured; connected/ready require a successful probe"
	switch {
	case c.connected && c.ready:
		msg = "Alpaca Broker API active"
	case c.probeMsg != "":
		msg = c.probeMsg
	}
	return Health{
		Configured:    true,
		Ready:         c.ready,
		Connected:     c.connected,
		Broker:        BrokerKindAlpaca,
		Name:          c.name,
		Environment:   c.Environment(),
		Message:       msg,
		LastCheckedAt: c.lastProbe,
	}
}

// ProbeConnectivity performs a lightweight authorized account request and caches
// the authoritative connectivity/readiness result. It is intended to be called
// occasionally (e.g. at reconciliation or on operator request), never on every
// readiness render.
func (c *AlpacaAdapter) ProbeConnectivity(ctx context.Context) error {
	if !c.IsConfigured() {
		return fmt.Errorf("broker not configured: alpaca credentials missing")
	}
	_, _, err := c.doRequest(ctx, "GET", "/v2/account", nil)

	c.mu.Lock()
	defer c.mu.Unlock()
	c.lastProbe = time.Now().UTC()
	if err != nil {
		c.connected = false
		c.ready = false
		c.probeMsg = "alpaca connectivity probe failed: " + err.Error()
		return err
	}
	c.connected = true
	c.ready = true
	c.probeMsg = ""
	return nil
}

func (c *AlpacaAdapter) GetBrokerSnapshot() (*reconciliation.BrokerState, error) {
	if !c.IsConfigured() {
		return nil, fmt.Errorf("broker not configured: alpaca credentials missing")
	}

	orders, err := c.ListOrders()
	if err != nil {
		return nil, fmt.Errorf("failed to list broker orders for snapshot: %w", err)
	}

	positions, err := c.ListPositions()
	if err != nil {
		return nil, fmt.Errorf("failed to list broker positions for snapshot: %w", err)
	}

	acct, err := c.GetAccountState()
	if err != nil {
		return nil, fmt.Errorf("failed to get broker account state for snapshot: %w", err)
	}

	c.mu.Lock()
	c.connected = true
	c.ready = true
	c.probeMsg = ""
	c.lastProbe = time.Now().UTC()
	c.mu.Unlock()

	now := time.Now().UTC()
	reconOrders := make(map[string]reconciliation.OrderState)
	for _, ord := range orders {
		reconOrders[ord.ClientOrderID] = reconciliation.OrderState{
			ClientOrderID: ord.ClientOrderID,
			BrokerOrderID: ord.BrokerOrderID,
			Symbol:        ord.Symbol,
			Side:          ord.Side,
			RequestedQty:  ord.Qty,
			FilledQty:     ord.FilledQty,
			Status:        string(ord.Status),
			CreatedAt:     ord.CreatedAt,
			UpdatedAt:     ord.UpdatedAt,
		}
	}

	reconPositions := make(map[string]reconciliation.PositionState)
	for _, pos := range positions {
		reconPositions[pos.Symbol] = reconciliation.PositionState{
			Symbol:      pos.Symbol,
			Qty:         pos.Qty,
			MarketValue: pos.MarketValue,
			CostBasis:   pos.CostBasis,
		}
	}

	return &reconciliation.BrokerState{
		Orders:    reconOrders,
		Positions: reconPositions,
		Cash:      acct.Cash,
		Equity:    acct.Equity,
		Timestamp: now,
	}, nil
}
