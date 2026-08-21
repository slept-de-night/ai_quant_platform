package webull

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"aq-engine-go/broker"
	"aq-engine-go/models"
)

// TestSubmitSandboxOrder_Success verifies sandbox order submission and normalization.
func TestSubmitSandboxOrder_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/trading/orders/place" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"order_id": "wb_ord_9988",
			"client_order_id": "client_order_sandbox_1",
			"symbol": "AAPL",
			"status": "SUBMITTED"
		}`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_sandbox_1",
		Environment: EnvSandbox,
	}

	adapter, err := NewAdapter("webull-sandbox", creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewAdapter failed: %v", err)
	}

	ord := &models.OrderIntent{
		Symbol:         "AAPL",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 150.0,
		ClientOrderID:  "client_order_sandbox_1",
	}

	bo, err := adapter.SubmitOrder(ord)
	if err != nil {
		t.Fatalf("SubmitOrder failed in sandbox: %v", err)
	}

	if bo.BrokerOrderID != "wb_ord_9988" {
		t.Fatalf("Expected BrokerOrderID 'wb_ord_9988', got '%s'", bo.BrokerOrderID)
	}
	if bo.ClientOrderID != "client_order_sandbox_1" {
		t.Fatalf("Expected ClientOrderID 'client_order_sandbox_1', got '%s'", bo.ClientOrderID)
	}
	if bo.Status != broker.BrokerOrderStatusAcknowledged {
		t.Fatalf("Expected normalized status ACKNOWLEDGED for SUBMITTED, got '%s'", bo.Status)
	}
}

// TestSubmitOrder_LiveEnvironmentBlocked verifies that live order submission is strictly prohibited.
func TestSubmitOrder_LiveEnvironmentBlocked(t *testing.T) {
	creds := Credentials{
		AppKey:      "wb_live_key",
		AppSecret:   "wb_live_secret",
		AccountID:   "acc_live_1",
		Environment: EnvLive,
	}

	adapter, err := NewAdapter("webull-live", creds)
	if err != nil {
		t.Fatalf("NewAdapter failed: %v", err)
	}

	ord := &models.OrderIntent{
		Symbol:        "NVDA",
		Side:          models.SideBuy,
		Qty:           5,
		ClientOrderID: "live_order_attempt_1",
	}

	_, err = adapter.SubmitOrder(ord)
	if err == nil {
		t.Fatalf("SubmitOrder MUST fail in LIVE environment under safety guard")
	}

	if !errors.Is(err, ErrLiveTradingNotPermitted) {
		t.Fatalf("Expected ErrLiveTradingNotPermitted, got: %v", err)
	}
}

// TestCancelSandboxOrder_Success verifies sandbox order cancellation.
func TestCancelSandboxOrder_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/trading/orders/cancel" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"success":true,"order_id":"wb_ord_9988","message":"order cancel request accepted"}`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_sandbox_1",
		Environment: EnvSandbox,
	}

	adapter, err := NewAdapter("webull-sandbox", creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewAdapter failed: %v", err)
	}

	err = adapter.CancelOrder("client_order_sandbox_1")
	if err != nil {
		t.Fatalf("CancelOrder failed in sandbox: %v", err)
	}
}

// TestCancelOrder_LiveEnvironmentBlocked verifies live cancel guard.
func TestCancelOrder_LiveEnvironmentBlocked(t *testing.T) {
	creds := Credentials{
		AppKey:      "wb_live_key",
		AppSecret:   "wb_live_secret",
		AccountID:   "acc_live_1",
		Environment: EnvLive,
	}

	adapter, err := NewAdapter("webull-live", creds)
	if err != nil {
		t.Fatalf("NewAdapter failed: %v", err)
	}

	err = adapter.CancelOrder("live_order_1")
	if err == nil {
		t.Fatalf("CancelOrder MUST fail in LIVE environment under safety guard")
	}

	if !errors.Is(err, ErrLiveTradingNotPermitted) {
		t.Fatalf("Expected ErrLiveTradingNotPermitted, got: %v", err)
	}
}

// TestQuerySandboxOrder_FoundAndAbsent verifies order query by ClientOrderID.
func TestQuerySandboxOrder_FoundAndAbsent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`[
			{
				"order_id": "ord_100",
				"client_order_id": "c_100",
				"symbol": "SPY",
				"side": "BUY",
				"total_quantity": "50",
				"filled_quantity": "50",
				"avg_price": "300.00",
				"status": "FILLED",
				"create_time": "2026-08-21T10:00:00Z",
				"update_time": "2026-08-21T10:00:00Z"
			}
		]`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_sandbox_1",
		Environment: EnvSandbox,
	}

	adapter, err := NewAdapter("webull-sandbox", creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewAdapter failed: %v", err)
	}

	// 1. Query existing order
	bo, err := adapter.GetOrder("c_100")
	if err != nil {
		t.Fatalf("GetOrder failed for existing order: %v", err)
	}
	if bo.Symbol != "SPY" || bo.Status != broker.BrokerOrderStatusFilled {
		t.Fatalf("Order mismatch: %+v", bo)
	}

	// 2. Query absent order
	_, err = adapter.GetOrder("non_existent_client_id")
	if err == nil {
		t.Fatalf("Expected error for absent order")
	}
	if !errors.Is(err, broker.ErrOrderNotFound) {
		t.Fatalf("Expected ErrOrderNotFound, got: %v", err)
	}
}
