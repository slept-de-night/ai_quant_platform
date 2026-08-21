package webull

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"aq-engine-go/broker"
	"aq-engine-go/models"
)

// TestFetchAccount_ParsesNormalizedState verifies JSON response deserialization and float conversion.
func TestFetchAccount_ParsesNormalizedState(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/trade/account/detail" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"account_id": "acc_test_99",
			"cash_balance": "125000.50",
			"total_equity": "150000.75",
			"buying_power": "200000.00",
			"currency": "USD"
		}`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_test_99",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	acc, err := FetchAccount(context.Background(), client, "acc_test_99")
	if err != nil {
		t.Fatalf("FetchAccount failed: %v", err)
	}

	if acc.Cash != 125000.50 {
		t.Fatalf("Expected cash 125000.50, got %.2f", acc.Cash)
	}
	if acc.Equity != 150000.75 {
		t.Fatalf("Expected equity 150000.75, got %.2f", acc.Equity)
	}
	if acc.BuyingPower != 200000.00 {
		t.Fatalf("Expected buying power 200000.00, got %.2f", acc.BuyingPower)
	}
	if acc.Currency != "USD" {
		t.Fatalf("Expected currency USD, got %s", acc.Currency)
	}
}

// TestFetchPositions_ParsesMultiplePositions verifies multi-symbol position parsing.
func TestFetchPositions_ParsesMultiplePositions(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/trade/account/positions" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`[
			{
				"symbol": "AAPL",
				"quantity": "50.0",
				"market_value": "7500.00",
				"cost_basis": "6000.00",
				"last_price": "150.00"
			},
			{
				"symbol": "NVDA",
				"quantity": "25.0",
				"market_value": "12500.00",
				"cost_basis": "10000.00",
				"last_price": "500.00"
			}
		]`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_test_99",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	positions, err := FetchPositions(context.Background(), client, "acc_test_99")
	if err != nil {
		t.Fatalf("FetchPositions failed: %v", err)
	}

	if len(positions) != 2 {
		t.Fatalf("Expected 2 positions, got %d", len(positions))
	}
	if positions[0].Symbol != "AAPL" || positions[0].Qty != 50.0 || positions[0].MarketValue != 7500.00 {
		t.Fatalf("Mismatch in position 0: %+v", positions[0])
	}
	if positions[1].Symbol != "NVDA" || positions[1].Qty != 25.0 || positions[1].MarketValue != 12500.00 {
		t.Fatalf("Mismatch in position 1: %+v", positions[1])
	}
}

// TestFetchOrders_NormalizesStatusAndDetails verifies orders deserialization and status normalization.
func TestFetchOrders_NormalizesStatusAndDetails(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/trade/order/list" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`[
			{
				"order_id": "ord_wb_001",
				"client_order_id": "cli_001",
				"symbol": "AAPL",
				"side": "BUY",
				"total_quantity": "10",
				"filled_quantity": "10",
				"avg_price": "150.25",
				"limit_price": "150.00",
				"status": "FILLED",
				"create_time": "2026-08-21T10:00:00Z",
				"update_time": "2026-08-21T10:01:00Z"
			},
			{
				"order_id": "ord_wb_002",
				"client_order_id": "cli_002",
				"symbol": "TSLA",
				"side": "SELL",
				"total_quantity": "20",
				"filled_quantity": "0",
				"avg_price": "0.0",
				"limit_price": "220.00",
				"status": "SUBMITTED",
				"create_time": "2026-08-21T10:05:00Z",
				"update_time": "2026-08-21T10:05:00Z"
			}
		]`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_test_99",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	orders, err := FetchOrders(context.Background(), client, "acc_test_99")
	if err != nil {
		t.Fatalf("FetchOrders failed: %v", err)
	}

	if len(orders) != 2 {
		t.Fatalf("Expected 2 orders, got %d", len(orders))
	}
	if orders[0].Status != broker.BrokerOrderStatusFilled {
		t.Fatalf("Expected status FILLED, got %s", orders[0].Status)
	}
	if orders[1].Status != broker.BrokerOrderStatusAcknowledged {
		t.Fatalf("Expected status ACKNOWLEDGED for SUBMITTED, got %s", orders[1].Status)
	}
}

// TestFetchBrokerSnapshot_ConstructsReconciliationBrokerState verifies end-to-end reconciliation snapshot creation.
func TestFetchBrokerSnapshot_ConstructsReconciliationBrokerState(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/v1/trade/account/detail":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"account_id":"acc_99","cash_balance":"100000.00","total_equity":"120000.00","currency":"USD"}`))
		case "/api/v1/trade/account/positions":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`[{"symbol":"MSFT","quantity":"50","market_value":"20000.00","cost_basis":"18000.00"}]`))
		case "/api/v1/trade/order/list":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`[{"order_id":"ord_1","client_order_id":"c1","symbol":"MSFT","side":"BUY","total_quantity":"50","filled_quantity":"50","avg_price":"360.0","status":"FILLED"}]`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_99",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	snapshot, err := FetchBrokerSnapshot(context.Background(), client, "acc_99")
	if err != nil {
		t.Fatalf("FetchBrokerSnapshot failed: %v", err)
	}

	if snapshot.Cash != 100000.00 || snapshot.Equity != 120000.00 {
		t.Fatalf("Snapshot cash/equity mismatch: cash=%.2f, eq=%.2f", snapshot.Cash, snapshot.Equity)
	}
	if len(snapshot.Positions) != 1 || snapshot.Positions["MSFT"].Qty != 50.0 {
		t.Fatalf("Snapshot positions mismatch: %+v", snapshot.Positions)
	}
	if len(snapshot.Orders) != 1 || snapshot.Orders["c1"].Symbol != "MSFT" {
		t.Fatalf("Snapshot orders mismatch: %+v", snapshot.Orders)
	}
}

// TestAdapter_ContractAndQuarantine verifies the Adapter interface implementation and submission quarantine.
func TestAdapter_ContractAndQuarantine(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/v1/trade/account/detail":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"account_id":"acc_99","cash_balance":"50000.00","total_equity":"50000.00","currency":"USD"}`))
		default:
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`[]`))
		}
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key",
		AppSecret:   "wb_test_secret",
		AccountID:   "acc_99",
		Environment: EnvSandbox,
	}

	adapter, err := NewAdapter("webull-test", creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewAdapter failed: %v", err)
	}

	// 1. Verify metadata
	if adapter.Name() != "webull-test" || adapter.Kind() != broker.BrokerKindWebull || adapter.Environment() != broker.EnvPaper {
		t.Fatalf("Adapter metadata mismatch")
	}

	// 2. Verify health connectivity probe
	health := adapter.GetHealth()
	if !health.Configured || !health.Connected {
		t.Fatalf("Expected health configured and connected, got: %+v", health)
	}

	// 3. Verify order submission is blocked by quarantine
	ord := &models.OrderIntent{
		Symbol:        "AAPL",
		Side:          models.SideBuy,
		Qty:           10,
		ClientOrderID: "quarantine-test-1",
	}
	_, submitErr := adapter.SubmitOrder(ord)
	if submitErr == nil {
		t.Fatalf("SubmitOrder MUST fail under quarantine in Phase W3")
	}

	// 4. Verify cancel order is blocked by quarantine
	cancelErr := adapter.CancelOrder("quarantine-test-1")
	if cancelErr == nil {
		t.Fatalf("CancelOrder MUST fail under quarantine in Phase W3")
	}

	// 5. Verify read-only account state works
	acc, err := adapter.GetAccountState()
	if err != nil || acc.Cash != 50000.00 {
		t.Fatalf("GetAccountState failed: %v", err)
	}
}
