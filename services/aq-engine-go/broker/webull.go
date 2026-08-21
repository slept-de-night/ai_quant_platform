package broker

import (
	"fmt"
	"net/http"
	"sync"
	"time"

	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

type WebullEnvironment string

const (
	WebullSandbox WebullEnvironment = "SANDBOX"
	WebullLive    WebullEnvironment = "LIVE"
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
	environment WebullEnvironment
}

func NewWebullAdapter(name, appKey, appSecret, accountID string, isPaper bool) *WebullAdapter {
	if name == "" {
		name = "webull-main"
	}
	env := WebullLive
	baseURL := "https://quoteapi.webullbroker.com/api"
	if isPaper {
		env = WebullSandbox
		baseURL = "https://quoteapi.webullfintech.com/api"
	}
	return &WebullAdapter{
		name:        name,
		appKey:      appKey,
		appSecret:   appSecret,
		accountID:   accountID,
		environment: env,
		baseURL:     baseURL,
		isPaper:     isPaper,
		client:      &http.Client{Timeout: 10 * time.Second},
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

func (w *WebullAdapter) WebullEnv() WebullEnvironment {
	return w.environment
}

func (w *WebullAdapter) IsConfigured() bool {
	return w.appKey != "" && w.appSecret != ""
}

func (w *WebullAdapter) Capabilities() BrokerCapabilities {
	// In Phase W0 quarantine: all capabilities are false until official OpenAPI client is certified.
	return BrokerCapabilities{
		SubmitOrder:     false,
		CancelOrder:     false,
		QueryOrder:      false,
		ListOrders:      false,
		ListPositions:   false,
		AccountState:    false,
		MarketData:      false,
		ExecutionEvents: false,
		Reconciliation:  false,
	}
}

func (w *WebullAdapter) SubmitOrder(order *models.OrderIntent) (*BrokerOrder, error) {
	if !w.IsConfigured() {
		return nil, ErrBrokerNotConfigured
	}
	return nil, fmt.Errorf("webull order submit unavailable: adapter quarantined pending official OpenAPI client (Phase W1)")
}

func (w *WebullAdapter) CancelOrder(clientOrderID string) error {
	if !w.IsConfigured() {
		return ErrBrokerNotConfigured
	}
	return fmt.Errorf("webull cancel order unavailable: adapter quarantined pending official OpenAPI client (Phase W1)")
}

func (w *WebullAdapter) GetOrder(clientOrderID string) (*BrokerOrder, error) {
	if !w.IsConfigured() {
		return nil, ErrBrokerNotConfigured
	}
	return nil, fmt.Errorf("webull get order unavailable: adapter quarantined pending official OpenAPI client (Phase W1)")
}

func (w *WebullAdapter) ListOrders() ([]BrokerOrder, error) {
	if !w.IsConfigured() {
		return nil, ErrBrokerNotConfigured
	}
	return nil, fmt.Errorf("webull list orders unavailable: adapter quarantined pending official OpenAPI client (Phase W1)")
}

func (w *WebullAdapter) ListPositions() ([]BrokerPosition, error) {
	if !w.IsConfigured() {
		return nil, ErrBrokerNotConfigured
	}
	return nil, fmt.Errorf("webull list positions unavailable: adapter quarantined pending official OpenAPI client (Phase W1)")
}

func (w *WebullAdapter) GetAccountState() (*AccountState, error) {
	if !w.IsConfigured() {
		return nil, ErrBrokerNotConfigured
	}
	return nil, fmt.Errorf("webull account state unavailable: adapter quarantined pending official OpenAPI client (Phase W1)")
}

func (w *WebullAdapter) GetHealth() Health {
	configured := w.IsConfigured()
	caps := w.Capabilities()
	msg := "Webull OpenAPI adapter is quarantined pending official OpenAPI sandbox implementation (Phase W1-W4)"
	if !configured {
		msg = "Webull adapter unconfigured (WEBULL_APP_KEY or WEBULL_APP_SECRET missing); not ready for broker execution"
	}
	return Health{
		Ready:         false, // Always false in Phase W0 quarantine
		Connected:     false,
		Configured:    configured,
		Broker:        BrokerKindWebull,
		Name:          w.name,
		Environment:   w.Environment(),
		Capabilities:  &caps,
		Message:       msg,
		LastCheckedAt: time.Now().UTC(),
	}
}

func (w *WebullAdapter) GetBrokerSnapshot() (*reconciliation.BrokerState, error) {
	if !w.IsConfigured() {
		return nil, ErrBrokerNotConfigured
	}
	return nil, fmt.Errorf("webull broker snapshot unavailable: adapter quarantined pending official OpenAPI client (Phase W1)")
}

