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
	// readOnly, when true, forces the adapter into a read-only / reconciliation
	// posture: economic writes are refused and every health/capability path
	// reports not-write-capable and not-ready until sandbox write certification.
	// Read-only broker truth (account, positions, orders, snapshot) still works.
	readOnly bool
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

// SetReadOnly toggles read-only quarantine mode. When enabled, economic writes
// are refused and the adapter reports not-ready until sandbox write cert.
func (a *Adapter) SetReadOnly(ro bool) {
	a.mu.Lock()
	a.readOnly = ro
	a.mu.Unlock()
}

func (a *Adapter) IsReadOnly() bool {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.readOnly
}

func (a *Adapter) Capabilities() broker.BrokerCapabilities {
	a.mu.RLock()
	ro := a.readOnly
	env := a.creds.Environment
	a.mu.RUnlock()

	isSandbox := env == EnvSandbox
	caps := broker.BrokerCapabilities{
		SubmitOrder:     isSandbox,
		CancelOrder:     isSandbox,
		QueryOrder:      true,
		ListOrders:      true,
		ListPositions:   true,
		AccountState:    true,
		MarketData:      false,
		ExecutionEvents: false,
		Reconciliation:  true,
	}
	// Read-only mode must never advertise economic write capability, even in
	// sandbox, until sandbox write certification passes.
	if ro {
		caps.SubmitOrder = false
		caps.CancelOrder = false
	}
	return caps
}

func (a *Adapter) SubmitOrder(order *models.OrderIntent) (*broker.BrokerOrder, error) {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	env := a.creds.Environment
	ro := a.readOnly
	a.mu.RUnlock()

	if ro {
		return nil, ErrReadOnlyQuarantine
	}
	return SubmitSandboxOrder(context.Background(), client, accountID, env, order)
}

func (a *Adapter) CancelOrder(clientOrderID string) error {
	a.mu.RLock()
	client := a.client
	accountID := a.accountID
	env := a.creds.Environment
	ro := a.readOnly
	a.mu.RUnlock()

	if ro {
		return ErrReadOnlyQuarantine
	}
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
	ro := a.IsReadOnly()
	caps := a.Capabilities()
	msg := "Webull OpenAPI adapter configured in read-only / reconciliation mode (Phase W3)"
	connected := false

	if !configured {
		msg = "Webull adapter unconfigured (missing app_key or app_secret)"
	} else if ro {
		msg = "Webull OpenAPI adapter configured in READ-ONLY quarantine mode (Phase W3): reads and reconciliation enabled; order writes disabled until sandbox write certification"
		// Probe connectivity via quick read-only account query.
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		if _, err := FetchAccount(ctx, a.client, a.accountID); err == nil {
			connected = true
		} else {
			connected = false
			msg = fmt.Sprintf("Webull read-only connectivity probe failed: %v", err)
		}
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

	// Read-only quarantine never reports Ready=true until sandbox write certification.
	ready := configured && connected && !ro

	return broker.Health{
		Ready:         ready,
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
