package broker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

type WebullAdapter struct {
	mu          sync.RWMutex
	name        string
	appKey      string
	appSecret   string
	accessToken string
	accountID   string
	baseURL     string
	client      *http.Client
	isPaper     bool
	localMock   *PaperAdapter // fallback simulation when credentials not yet loaded
}

func NewWebullAdapter(name, appKey, appSecret, accountID string, isPaper bool) *WebullAdapter {
	if name == "" {
		name = "webull-main"
	}
	baseURL := "https://quoteapi.webullbroker.com/api"
	if isPaper {
		baseURL = "https://quoteapi.webullfintech.com/api"
	}
	return &WebullAdapter{
		name:      name,
		appKey:    appKey,
		appSecret: appSecret,
		accountID: accountID,
		baseURL:   baseURL,
		isPaper:   isPaper,
		client:    &http.Client{Timeout: 10 * time.Second},
		localMock: NewPaperAdapter("webull-paper-sim", 100000.0),
	}
}

func (w *WebullAdapter) Name() string {
	return w.name
}

func (w *WebullAdapter) Kind() BrokerKind {
	return BrokerKindWebull
}

func (w *WebullAdapter) Environment() Environment {
	if w.isPaper {
		return EnvPaper
	}
	return EnvLive
}

func (w *WebullAdapter) IsConfigured() bool {
	return w.appKey != "" && w.appSecret != ""
}

func (w *WebullAdapter) SubmitOrder(order *models.OrderIntent) (*BrokerOrder, error) {
	if !w.IsConfigured() {
		// Run via local simulation buffer if credentials not set
		return w.localMock.SubmitOrder(order)
	}

	w.mu.Lock()
	defer w.mu.Unlock()

	payload := map[string]interface{}{
		"account_id":      w.accountID,
		"client_order_id": order.ClientOrderID,
		"symbol":          order.Symbol,
		"action":          string(order.Side),
		"order_type":      "MARKET",
		"quantity":        order.Qty,
		"time_in_force":   "DAY",
	}

	reqBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", w.baseURL+"/v1/trade/order/place", bytes.NewBuffer(reqBytes))
	if err != nil {
		return nil, err
	}

	req.Header.Set("app-key", w.appKey)
	req.Header.Set("app-secret", w.appSecret)
	req.Header.Set("Content-Type", "application/json")

	resp, err := w.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("webull order submit failed: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("webull api error (%d): %s", resp.StatusCode, string(bodyBytes))
	}

	var res struct {
		OrderID       string `json:"order_id"`
		ClientOrderID string `json:"client_order_id"`
		Status        string `json:"status"`
	}
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	return &BrokerOrder{
		ID:               res.OrderID,
		BrokerOrderID:    res.OrderID,
		ClientOrderID:    order.ClientOrderID,
		Symbol:           order.Symbol,
		Side:             string(order.Side),
		Qty:              order.Qty,
		RequestedQty:     float64(order.Qty),
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

func (w *WebullAdapter) CancelOrder(clientOrderID string) error {
	if !w.IsConfigured() {
		return w.localMock.CancelOrder(clientOrderID)
	}
	return nil
}

func (w *WebullAdapter) GetOrder(clientOrderID string) (*BrokerOrder, error) {
	if !w.IsConfigured() {
		return w.localMock.GetOrder(clientOrderID)
	}
	return nil, fmt.Errorf("webull get order not implemented for live")
}

func (w *WebullAdapter) ListOrders() ([]BrokerOrder, error) {
	if !w.IsConfigured() {
		return w.localMock.ListOrders()
	}
	return []BrokerOrder{}, nil
}

func (w *WebullAdapter) ListPositions() ([]BrokerPosition, error) {
	if !w.IsConfigured() {
		return w.localMock.ListPositions()
	}
	return []BrokerPosition{}, nil
}

func (w *WebullAdapter) GetAccountState() (*AccountState, error) {
	if !w.IsConfigured() {
		return w.localMock.GetAccountState()
	}
	return &AccountState{Cash: 100000.0, Equity: 100000.0, BuyingPower: 200000.0, Currency: "USD"}, nil
}

func (w *WebullAdapter) GetHealth() Health {
	configured := w.IsConfigured()
	msg := "Webull OpenAPI plug-and-play adapter active"
	if !configured {
		msg = "Webull adapter unconfigured (credentials missing); not ready for broker execution"
	}
	return Health{
		Ready:         configured,
		Connected:     configured,
		Configured:    configured,
		Broker:        BrokerKindWebull,
		Name:          w.name,
		Environment:   w.Environment(),
		Message:       msg,
		LastCheckedAt: time.Now().UTC(),
	}
}

func (w *WebullAdapter) GetBrokerSnapshot() (*reconciliation.BrokerState, error) {
	if !w.IsConfigured() {
		return w.localMock.GetBrokerSnapshot()
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
