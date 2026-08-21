package webull

import (
	"context"
	"fmt"
	"sync"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

// Adapter implements the broker.BrokerAdapter interface for Webull OpenAPI.
type Adapter struct {
	mu        sync.RWMutex
	name      string
	creds     Credentials
	client    *Client
	accountID string
}

// NewAdapter creates a new Webull OpenAPI broker adapter.
func NewAdapter(name string, creds Credentials, opts ...ClientOption) (*Adapter, error) {
	if name == "" {
		name = "webull-main"
	}

	var client *Client
	if creds.AppKey != "" && creds.AppSecret != "" {
		c, err := NewClient(creds, opts...)
		if err != nil {
			return nil, fmt.Errorf("failed to initialize webull client: %w", err)
		}
		client = c
	}

	return &Adapter{
		name:      name,
		creds:     creds,
		client:    client,
		accountID: creds.AccountID,
	}, nil
}

func (a *Adapter) Name() string {
	return a.name
}

func (a *Adapter) Kind() broker.BrokerKind {
	return broker.BrokerKindWebull
}

func (a *Adapter) Environment() broker.Environment {
	if a.creds.Environment == EnvSandbox {
		return broker.EnvPaper
	}
	return broker.EnvLive
}

func (a *Adapter) IsConfigured() bool {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.client != nil && a.creds.AppKey != "" && a.creds.AppSecret != ""
}

func (a *Adapter) Capabilities() broker.BrokerCapabilities {
	isSandbox := a.creds.Environment == EnvSandbox
	return broker.BrokerCapabilities{
		SubmitOrder:     isSandbox, // Permitted in sandbox, strictly guarded in live
		CancelOrder:     isSandbox, // Permitted in sandbox, strictly guarded in live
		QueryOrder:      true,
		ListOrders:      true,
		ListPositions:   true,
		AccountState:    true,
		MarketData:      false,
		ExecutionEvents: false,
		Reconciliation:  true,
	}
}

func (a *Adapter) SubmitOrder(order *models.OrderIntent) (*broker.BrokerOrder, error) {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	env := a.creds.Environment
	a.mu.RUnlock()

	return SubmitSandboxOrder(context.Background(), client, accountID, env, order)
}

func (a *Adapter) CancelOrder(clientOrderID string) error {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	env := a.creds.Environment
	a.mu.RUnlock()

	return CancelSandboxOrder(context.Background(), client, accountID, env, clientOrderID)
}

func (a *Adapter) GetOrder(clientOrderID string) (*broker.BrokerOrder, error) {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	a.mu.RUnlock()

	return QuerySandboxOrder(context.Background(), client, accountID, clientOrderID)
}

func (a *Adapter) ListOrders() ([]broker.BrokerOrder, error) {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	a.mu.RUnlock()

	if client == nil {
		return nil, broker.ErrBrokerNotConfigured
	}
	return FetchOrders(context.Background(), client, accountID)
}

func (a *Adapter) ListPositions() ([]broker.BrokerPosition, error) {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	a.mu.RUnlock()

	if client == nil {
		return nil, broker.ErrBrokerNotConfigured
	}
	return FetchPositions(context.Background(), client, accountID)
}

func (a *Adapter) GetAccountState() (*broker.AccountState, error) {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	a.mu.RUnlock()

	if client == nil {
		return nil, broker.ErrBrokerNotConfigured
	}
	return FetchAccount(context.Background(), client, accountID)
}

func (a *Adapter) GetBrokerSnapshot() (*reconciliation.BrokerState, error) {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	a.mu.RUnlock()

	if client == nil {
		return nil, broker.ErrBrokerNotConfigured
	}
	return FetchBrokerSnapshot(context.Background(), client, accountID)
}

func (a *Adapter) GetHealth() broker.Health {
	configured := a.IsConfigured()
	caps := a.Capabilities()
	msg := "Webull OpenAPI adapter configured in read-only / reconciliation mode (Phase W3)"
	connected := false

	if !configured {
		msg = "Webull adapter unconfigured (missing app_key or app_secret)"
	} else {
		// Probe connectivity via quick read-only account query
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		if _, err := FetchAccount(ctx, a.client, a.accountID); err == nil {
			connected = true
		} else {
			msg = fmt.Sprintf("Webull connectivity probe failed: %v", err)
		}
	}

	return broker.Health{
		Ready:         configured && connected,
		Connected:     connected,
		Configured:    configured,
		Broker:        broker.BrokerKindWebull,
		Name:          a.name,
		Environment:   a.Environment(),
		Capabilities:  &caps,
		Message:       msg,
		LastCheckedAt: time.Now().UTC(),
	}
}
