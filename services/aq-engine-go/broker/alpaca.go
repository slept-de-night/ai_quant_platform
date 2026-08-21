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
	"strings"
	"time"

	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

type AlpacaAdapter struct {
	name      string
	apiKey    string
	secretKey string
	baseURL   string
	client    *http.Client
	localMock *PaperAdapter
}

func NewAlpacaPaperClient(apiKey, secretKey string) *AlpacaAdapter {
	return NewAlpacaAdapter("alpaca-paper", apiKey, secretKey, true)
}

func NewAlpacaAdapter(name, apiKey, secretKey string, isPaper bool) *AlpacaAdapter {
	baseURL := "https://paper-api.alpaca.markets"
	if !isPaper {
		baseURL = "https://api.alpaca.markets"
	}
	if name == "" {
		name = "alpaca-paper"
	}
	return &AlpacaAdapter{
		name:      name,
		apiKey:    apiKey,
		secretKey: secretKey,
		baseURL:   baseURL,
		client:    &http.Client{Timeout: 10 * time.Second},
		localMock: NewPaperAdapter("alpaca-mock-paper", 100000.0),
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

func (c *AlpacaAdapter) Environment() Environment {
	if strings.Contains(c.baseURL, "paper") || strings.Contains(c.baseURL, "127.0.0.1") || strings.Contains(c.baseURL, "localhost") {
		return EnvPaper
	}
	return EnvLive
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

func parseAlpacaOrder(res alpacaOrderResponse) BrokerOrder {
	qtyInt, _ := strconv.Atoi(res.Qty)
	filledQtyInt, _ := strconv.Atoi(res.FilledQty)

	var avgFillPrice float64
	if res.FilledAvgPrice != nil {
		avgFillPrice, _ = strconv.ParseFloat(*res.FilledAvgPrice, 64)
	}

	var limitPrice float64
	if res.LimitPrice != nil {
		limitPrice, _ = strconv.ParseFloat(*res.LimitPrice, 64)
	}

	createdAt, _ := time.Parse(time.RFC3339Nano, res.CreatedAt)
	if createdAt.IsZero() {
		createdAt = time.Now().UTC()
	}
	updatedAt, _ := time.Parse(time.RFC3339Nano, res.UpdatedAt)
	if updatedAt.IsZero() {
		updatedAt = createdAt
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
	}
}

func (c *AlpacaAdapter) SubmitOrder(order *models.OrderIntent) (*BrokerOrder, error) {
	if !c.IsConfigured() {
		return c.localMock.SubmitOrder(order)
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

	bo := parseAlpacaOrder(res)
	if bo.LimitPrice == 0 {
		bo.LimitPrice = order.ReferencePrice
	}
	return &bo, nil
}

func (c *AlpacaAdapter) CancelOrder(clientOrderID string) error {
	if !c.IsConfigured() {
		return c.localMock.CancelOrder(clientOrderID)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	endpoint := fmt.Sprintf("/v2/orders:by_client_order_id?client_order_id=%s", url.QueryEscape(clientOrderID))
	_, _, err := c.doRequest(ctx, "DELETE", endpoint, nil)
	return err
}

func (c *AlpacaAdapter) GetOrder(clientOrderID string) (*BrokerOrder, error) {
	if !c.IsConfigured() {
		return c.localMock.GetOrder(clientOrderID)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	endpoint := fmt.Sprintf("/v2/orders:by_client_order_id?client_order_id=%s", url.QueryEscape(clientOrderID))
	bodyBytes, _, err := c.doRequest(ctx, "GET", endpoint, nil)
	if err != nil {
		return nil, err
	}

	var res alpacaOrderResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, fmt.Errorf("failed to parse alpaca order response: %w", err)
	}

	bo := parseAlpacaOrder(res)
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

	bo := parseAlpacaOrder(res)
	return &bo, nil
}

func (c *AlpacaAdapter) ListOrders() ([]BrokerOrder, error) {
	if !c.IsConfigured() {
		return c.localMock.ListOrders()
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	bodyBytes, _, err := c.doRequest(ctx, "GET", "/v2/orders?status=all&limit=100", nil)
	if err != nil {
		return nil, err
	}

	var resList []alpacaOrderResponse
	if err := json.Unmarshal(bodyBytes, &resList); err != nil {
		return nil, fmt.Errorf("failed to parse alpaca order list: %w", err)
	}

	orders := make([]BrokerOrder, len(resList))
	for i, res := range resList {
		orders[i] = parseAlpacaOrder(res)
	}
	return orders, nil
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
		return c.localMock.ListPositions()
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
		qty, _ := strconv.ParseFloat(pos.Qty, 64)
		mv, _ := strconv.ParseFloat(pos.MarketValue, 64)
		cb, _ := strconv.ParseFloat(pos.CostBasis, 64)
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
		return c.localMock.GetAccountState()
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

	cash, _ := strconv.ParseFloat(res.Cash, 64)
	equity, _ := strconv.ParseFloat(res.Equity, 64)
	buyingPower, _ := strconv.ParseFloat(res.BuyingPower, 64)

	return &AccountState{
		Cash:        cash,
		Equity:      equity,
		BuyingPower: buyingPower,
		Currency:    res.Currency,
	}, nil
}

func (c *AlpacaAdapter) GetHealth() Health {
	configured := c.IsConfigured()
	msg := "Alpaca Broker API active"
	if !configured {
		msg = "Alpaca adapter running in mock paper simulation"
	}
	return Health{
		Ready:         true,
		Connected:     configured,
		Configured:    configured,
		Broker:        BrokerKindAlpaca,
		Name:          c.name,
		Environment:   c.Environment(),
		Message:       msg,
		LastCheckedAt: time.Now().UTC(),
	}
}

func (c *AlpacaAdapter) GetBrokerSnapshot() (*reconciliation.BrokerState, error) {
	if !c.IsConfigured() {
		return c.localMock.GetBrokerSnapshot()
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
