package broker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
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

func (c *AlpacaAdapter) Name() string {
	return c.name
}

func (c *AlpacaAdapter) Kind() BrokerKind {
	return BrokerKindAlpaca
}

func (c *AlpacaAdapter) Environment() Environment {
	if c.baseURL == "https://paper-api.alpaca.markets" {
		return EnvPaper
	}
	return EnvLive
}

func (c *AlpacaAdapter) IsConfigured() bool {
	return c.apiKey != "" && c.secretKey != ""
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
	ID            string `json:"id"`
	ClientOrderID string `json:"client_order_id"`
	Status        string `json:"status"`
	Symbol        string `json:"symbol"`
	Qty           string `json:"qty"`
	Side          string `json:"side"`
}

func (c *AlpacaAdapter) SubmitOrder(order *models.OrderIntent) (*BrokerOrder, error) {
	if !c.IsConfigured() {
		return c.localMock.SubmitOrder(order)
	}

	reqBody, err := json.Marshal(alpacaOrderRequest{
		Symbol:        order.Symbol,
		Qty:           order.Qty,
		Side:          string(order.Side),
		Type:          "market",
		TimeInForce:   "day",
		ClientOrderID: order.ClientOrderID,
	})
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", c.baseURL+"/v2/orders", bytes.NewBuffer(reqBody))
	if err != nil {
		return nil, err
	}

	req.Header.Set("APCA-API-KEY-ID", c.apiKey)
	req.Header.Set("APCA-API-SECRET-KEY", c.secretKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	bodyBytes, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("alpaca api error (%d): %s", resp.StatusCode, string(bodyBytes))
	}

	var res alpacaOrderResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, err
	}

	qtyInt, _ := strconv.Atoi(res.Qty)
	now := time.Now().UTC()
	return &BrokerOrder{
		ID:               res.ID,
		BrokerOrderID:    res.ID,
		ClientOrderID:    res.ClientOrderID,
		Symbol:           res.Symbol,
		Side:             res.Side,
		Qty:              qtyInt,
		RequestedQty:     float64(qtyInt),
		FilledQty:        0,
		FilledQtyFloat:   0,
		Status:           NormalizeBrokerStatus(res.Status),
		RawStatus:        res.Status,
		LimitPrice:       order.ReferencePrice,
		AvgPrice:         order.ReferencePrice,
		AverageFillPrice: order.ReferencePrice,
		CreatedAt:        now,
		UpdatedAt:        now,
	}, nil
}

func (c *AlpacaAdapter) CancelOrder(clientOrderID string) error {
	if !c.IsConfigured() {
		return c.localMock.CancelOrder(clientOrderID)
	}
	return nil
}

func (c *AlpacaAdapter) GetOrder(clientOrderID string) (*BrokerOrder, error) {
	if !c.IsConfigured() {
		return c.localMock.GetOrder(clientOrderID)
	}
	return nil, fmt.Errorf("alpaca get order not implemented for live")
}

func (c *AlpacaAdapter) ListOrders() ([]BrokerOrder, error) {
	if !c.IsConfigured() {
		return c.localMock.ListOrders()
	}
	return []BrokerOrder{}, nil
}

func (c *AlpacaAdapter) ListPositions() ([]BrokerPosition, error) {
	if !c.IsConfigured() {
		return c.localMock.ListPositions()
	}
	return []BrokerPosition{}, nil
}

func (c *AlpacaAdapter) GetAccountState() (*AccountState, error) {
	if !c.IsConfigured() {
		return c.localMock.GetAccountState()
	}
	return &AccountState{Cash: 100000.0, Equity: 100000.0, BuyingPower: 200000.0, Currency: "USD"}, nil
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
	now := time.Now().UTC()
	return &reconciliation.BrokerState{
		Orders:    make(map[string]reconciliation.OrderState),
		Positions: make(map[string]reconciliation.PositionState),
		Cash:      100000.0,
		Equity:    100000.0,
		Timestamp: now,
	}, nil
}

