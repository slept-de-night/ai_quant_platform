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
		if r.URL.Path != "/trading/assets/balances/get" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"total_asset_currency": "USD",
			"total_cash_balance": "125000.50",
			"total_market_value": "25000.25",
			"total_unrealized_profit_loss": "3000.45",
			"total_net_liquidation_value": "150000.75",
			"total_day_profit_loss": "120.10",
			"account_currency_assets": [
				{
					"currency": "USD",
					"cash_balance": "125000.50",
					"buying_power": "200000.00",
					"net_liquidation_value": "150000.75"
				}
			]
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
		if r.URL.Path != "/trading/assets/positions/list" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`[
			{
				"position_id": "pos_a_1",
				"currency": "USD",
				"quantity": "50.0",
				"symbol": "AAPL",
				"instrument_type": "EQUITY",
				"last_price": "150.00",
				"cost_price": "120.00",
				"unrealized_profit_loss": "1500.00",
				"option_strategy": "SINGLE"
			},
			{
				"position_id": "pos_a_2",
				"currency": "USD",
				"quantity": "25.0",
				"symbol": "NVDA",
				"instrument_type": "EQUITY",
				"last_price": "500.00",
				"cost_price": "400.00",
				"unrealized_profit_loss": "2500.00",
				"option_strategy": "SINGLE"
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
	if positions[0].Symbol != "AAPL" || positions[0].Qty != 50.0 || positions[0].MarketValue != 7500.00 || positions[0].CostBasis != 6000.00 {
		t.Fatalf("Mismatch in position 0: %+v", positions[0])
	}
	if positions[1].Symbol != "NVDA" || positions[1].Qty != 25.0 || positions[1].MarketValue != 12500.00 || positions[1].CostBasis != 10000.00 {
		t.Fatalf("Mismatch in position 1: %+v", positions[1])
	}
}

// TestFetchOrders_NormalizesStatusAndDetails verifies orders deserialization and status normalization.
func TestFetchOrders_NormalizesStatusAndDetails(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/trading/orders/open-orders/list" {
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
		case "/trading/assets/balances/get":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"total_asset_currency":"USD","total_cash_balance":"100000.00","total_market_value":"20000.00","total_net_liquidation_value":"120000.00","account_currency_assets":[{"currency":"USD","cash_balance":"100000.00","buying_power":"130000.00"}]}`))
		case "/trading/assets/positions/list":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`[{"position_id":"pos_msft_1","currency":"USD","quantity":"50","symbol":"MSFT","instrument_type":"EQUITY","last_price":"400.00","cost_price":"360.00","unrealized_profit_loss":"2000.00","option_strategy":"SINGLE"}]`))
		case "/trading/orders/open-orders/list":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`[{"order_id":"ord_1","client_order_id":"c1","symbol":"MSFT","side":"BUY","total_quantity":"50","filled_quantity":"50","avg_price":"360.0","status":"FILLED","create_time":"2026-08-21T10:00:00Z","update_time":"2026-08-21T10:00:00Z"}]`))
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
		case "/trading/assets/balances/get":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"total_asset_currency":"USD","total_cash_balance":"50000.00","total_net_liquidation_value":"50000.00","account_currency_assets":[{"currency":"USD","cash_balance":"50000.00","buying_power":"60000.00"}]}`))
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

// TestAdapter_ReadOnlyMode verifies the D7 read-only watchdog: economic writes are
// refused, capabilities never advertise submit/cancel, and Ready stays false even
// when read-only connectivity succeeds. Reads and reconciliation still work.
func TestAdapter_ReadOnlyMode(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/trading/assets/balances/get":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"total_asset_currency":"USD","total_cash_balance":"50000.00","total_net_liquidation_value":"50000.00","account_currency_assets":[{"currency":"USD","cash_balance":"50000.00","buying_power":"60000.00"}]}`))
		case "/trading/orders/open-orders/list":
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`[]`))
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

	adapter, err := NewAdapter("webull-readonly", creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewAdapter failed: %v", err)
	}
	adapter.SetReadOnly(true)

	if !adapter.IsReadOnly() {
		t.Fatalf("expected IsReadOnly=true after SetReadOnly(true)")
	}

	// 1. Capabilities must never advertise economic writes in read-only mode.
	caps := adapter.Capabilities()
	if caps.SubmitOrder || caps.CancelOrder || caps.ExecutionEvents {
		t.Fatalf("read-only capabilities must not advertise writes; got %+v", caps)
	}
	if !caps.QueryOrder || !caps.ListOrders || !caps.ListPositions || !caps.AccountState || !caps.Reconciliation {
		t.Fatalf("read-only capabilities must expose broker truth + reconciliation; got %+v", caps)
	}

	// 2. Submit/Cancel refused with ErrReadOnlyQuarantine even in sandbox.
	ord := &models.OrderIntent{Symbol: "AAPL", Side: models.SideBuy, Qty: 10, ClientOrderID: "ro-1"}
	if _, err := adapter.SubmitOrder(ord); err != ErrReadOnlyQuarantine {
		t.Fatalf("expected ErrReadOnlyQuarantine on SubmitOrder in read-only mode, got %v", err)
	}
	if err := adapter.CancelOrder("ro-1"); err != ErrReadOnlyQuarantine {
		t.Fatalf("expected ErrReadOnlyQuarantine on CancelOrder in read-only mode, got %v", err)
	}

	// 3. Health: connected + configured true, but Ready=false while read-only.
	health := adapter.GetHealth()
	if !health.Configured || !health.Connected {
		t.Fatalf("expected read-only health configured+connected, got %+v", health)
	}
	if health.Ready {
		t.Fatalf("read-only adapter must report Ready=false until sandbox write cert; got %+v", health)
	}
	if caps2 := health.Capabilities; caps2 == nil || caps2.SubmitOrder || caps2.CancelOrder || caps2.ExecutionEvents {
		t.Fatalf("read-only health capabilities must not advertise writes; got %+v", caps2)
	}

	// 4. Reads still work in read-only mode.
	acc, err := adapter.GetAccountState()
	if err != nil || acc.Cash != 50000.00 {
		t.Fatalf("read-only GetAccountState failed: %v (cash=%.2f)", err, acc.Cash)
	}
	if _, err := adapter.ListOrders(); err != nil {
		t.Fatalf("read-only ListOrders failed: %v", err)
	}
	if _, err := adapter.GetBrokerSnapshot(); err != nil {
		t.Fatalf("read-only GetBrokerSnapshot failed: %v", err)
	}

	// 5. Exiting read-only restores sandbox write capability advertisement.
	adapter.SetReadOnly(false)
	if adapter.IsReadOnly() {
		t.Fatalf("expected IsReadOnly=false after SetReadOnly(false)")
	}
	if !adapter.Capabilities().SubmitOrder || !adapter.Capabilities().CancelOrder {
		t.Fatalf("sandbox adapter should advertise writes after leaving read-only mode")
	}
}
