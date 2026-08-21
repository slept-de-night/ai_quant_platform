package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"aq-engine-go/models"
)

func TestAlpacaSubmitSuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("APCA-API-KEY-ID") != "test-key" || r.Header.Get("APCA-API-SECRET-KEY") != "test-secret" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		if r.URL.Path == "/v2/orders" && r.Method == "POST" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(alpacaOrderResponse{
				ID:             "alpaca-ord-123",
				ClientOrderID:  "client-1",
				CreatedAt:      "2026-08-21T08:00:00Z",
				UpdatedAt:      "2026-08-21T08:00:01Z",
				Symbol:         "NVDA",
				Qty:            "10",
				FilledQty:      "0",
				Side:           "buy",
				Type:           "market",
				TimeInForce:    "day",
				FilledAvgPrice: nil,
				Status:         "accepted",
			})
			return
		}
		http.NotFound(w, r)
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	order := &models.OrderIntent{
		Symbol:         "NVDA",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 130.0,
		ClientOrderID:  "client-1",
	}

	bo, err := client.SubmitOrder(order)
	if err != nil {
		t.Fatalf("SubmitOrder failed: %v", err)
	}

	if bo.BrokerOrderID != "alpaca-ord-123" || bo.ClientOrderID != "client-1" {
		t.Fatalf("Unexpected order identifiers: %+v", bo)
	}
	if bo.Status != BrokerOrderStatusAcknowledged {
		t.Fatalf("Expected ACKNOWLEDGED, got %s", bo.Status)
	}
	if bo.RequestedQty != 10.0 {
		t.Fatalf("Expected RequestedQty=10, got %.2f", bo.RequestedQty)
	}
}

func TestAlpacaSubmitRejection(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		w.Write([]byte(`{"code": 40310000, "message": "insufficient buying power"}`))
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	order := &models.OrderIntent{
		Symbol:        "TSLA",
		Side:          models.SideBuy,
		Qty:           100,
		ClientOrderID: "client-rej-1",
	}

	_, err := client.SubmitOrder(order)
	if err == nil {
		t.Fatalf("Expected submit rejection error, got nil")
	}
	if !strings.Contains(err.Error(), "insufficient buying power") {
		t.Fatalf("Expected error message to contain reason, got: %v", err)
	}
	// Verify secret is NOT in error message
	if strings.Contains(err.Error(), "test-secret") || strings.Contains(err.Error(), "test-key") {
		t.Fatalf("Secret key leaked in error message: %v", err)
	}
}

func TestAlpacaGetOrderAndPartialFill(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v2/orders:by_client_order_id" && r.Method == "GET" {
			avgPrice := "450.25"
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(alpacaOrderResponse{
				ID:             "alp-fill-1",
				ClientOrderID:  "client-partial-1",
				CreatedAt:      "2026-08-21T08:00:00Z",
				UpdatedAt:      "2026-08-21T08:00:01Z",
				Symbol:         "QQQ",
				Qty:            "20",
				FilledQty:      "8",
				Side:           "buy",
				FilledAvgPrice: &avgPrice,
				Status:         "partially_filled",
			})
			return
		}
		http.NotFound(w, r)
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	bo, err := client.GetOrder("client-partial-1")
	if err != nil {
		t.Fatalf("GetOrder failed: %v", err)
	}

	if bo.Status != BrokerOrderStatusPartiallyFilled {
		t.Fatalf("Expected PARTIALLY_FILLED, got %s", bo.Status)
	}
	if bo.FilledQty != 8 || bo.RequestedQty != 20 {
		t.Fatalf("Expected filled 8/20, got %d/%.0f", bo.FilledQty, bo.RequestedQty)
	}
	if bo.AverageFillPrice != 450.25 {
		t.Fatalf("Expected avg fill price 450.25, got %.2f", bo.AverageFillPrice)
	}
}

func TestAlpacaListOrdersPositionsAccount(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v2/orders":
			filledPrice := "130.50"
			json.NewEncoder(w).Encode([]alpacaOrderResponse{
				{
					ID:             "alp-1",
					ClientOrderID:  "c-1",
					CreatedAt:      "2026-08-21T08:00:00Z",
					UpdatedAt:      "2026-08-21T08:00:01Z",
					Symbol:         "NVDA",
					Qty:            "10",
					FilledQty:      "10",
					Side:           "buy",
					FilledAvgPrice: &filledPrice,
					Status:         "filled",
				},
			})
		case "/v2/positions":
			json.NewEncoder(w).Encode([]alpacaPositionResponse{
				{
					Symbol:       "NVDA",
					Qty:          "10",
					MarketValue:  "1305.00",
					CostBasis:    "1300.00",
					CurrentPrice: "130.50",
				},
			})
		case "/v2/account":
			json.NewEncoder(w).Encode(alpacaAccountResponse{
				Cash:        "98695.00",
				Equity:      "100000.00",
				BuyingPower: "197390.00",
				Currency:    "USD",
				Status:      "ACTIVE",
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	// 1. ListOrders
	orders, err := client.ListOrders()
	if err != nil || len(orders) != 1 {
		t.Fatalf("ListOrders failed: %v, count=%d", err, len(orders))
	}
	if orders[0].Status != BrokerOrderStatusFilled || orders[0].FilledQty != 10 {
		t.Fatalf("Unexpected order parsed: %+v", orders[0])
	}

	// 2. ListPositions
	positions, err := client.ListPositions()
	if err != nil || len(positions) != 1 {
		t.Fatalf("ListPositions failed: %v, count=%d", err, len(positions))
	}
	if positions[0].Symbol != "NVDA" || positions[0].Qty != 10.0 || positions[0].MarketValue != 1305.00 {
		t.Fatalf("Unexpected position parsed: %+v", positions[0])
	}

	// 3. GetAccountState
	acct, err := client.GetAccountState()
	if err != nil {
		t.Fatalf("GetAccountState failed: %v", err)
	}
	if acct.Cash != 98695.00 || acct.Equity != 100000.00 {
		t.Fatalf("Unexpected account parsed: %+v", acct)
	}

	// 4. GetBrokerSnapshot
	snapshot, err := client.GetBrokerSnapshot()
	if err != nil {
		t.Fatalf("GetBrokerSnapshot failed: %v", err)
	}
	if len(snapshot.Orders) != 1 || len(snapshot.Positions) != 1 || snapshot.Cash != 98695.00 {
		t.Fatalf("Unexpected snapshot: %+v", snapshot)
	}
}

func TestAlpacaCancelSuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v2/orders:by_client_order_id" && r.Method == "DELETE" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		http.NotFound(w, r)
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	if err := client.CancelOrder("client-cancel-1"); err != nil {
		t.Fatalf("CancelOrder failed: %v", err)
	}
}

func TestAlpacaHTTPErrorCodes(t *testing.T) {
	// 1. Test 429 Rate Limit
	s429 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
		w.Write([]byte(`{"message": "too many requests"}`))
	}))
	defer s429.Close()

	c429 := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	c429.SetBaseURL(s429.URL)
	_, err429 := c429.GetAccountState()
	if err429 == nil || !strings.Contains(err429.Error(), "429") {
		t.Fatalf("Expected 429 error, got: %v", err429)
	}

	// 2. Test 500 Internal Error
	s500 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{"message": "internal server error"}`))
	}))
	defer s500.Close()

	c500 := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	c500.SetBaseURL(s500.URL)
	_, err500 := c500.ListPositions()
	if err500 == nil || !strings.Contains(err500.Error(), "500") {
		t.Fatalf("Expected 500 error, got: %v", err500)
	}

	// 3. Test Malformed JSON
	sMalformed := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{not-valid-json`))
	}))
	defer sMalformed.Close()

	cMalformed := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	cMalformed.SetBaseURL(sMalformed.URL)
	_, errMalformed := cMalformed.ListOrders()
	if errMalformed == nil {
		t.Fatalf("Expected malformed JSON error, got nil")
	}
}

func TestAlpacaTimeout(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(100 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)
	client.client.Timeout = 10 * time.Millisecond // very short timeout to trigger deadline

	_, err := client.GetAccountState()
	if err == nil {
		t.Fatalf("Expected timeout error, got nil")
	}
}

func TestAlpacaUnconfiguredDoesNotMasquerade(t *testing.T) {
	client := NewAlpacaAdapter("alpaca-paper", "", "", true)

	order := &models.OrderIntent{
		Symbol:        "NVDA",
		Side:          models.SideBuy,
		Qty:           10,
		ClientOrderID: "unconfigured-1",
	}

	if _, err := client.SubmitOrder(order); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("SubmitOrder: expected broker not configured error, got %v", err)
	}
	if err := client.CancelOrder("unconfigured-1"); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("CancelOrder: expected broker not configured error, got %v", err)
	}
	if _, err := client.GetOrder("unconfigured-1"); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("GetOrder: expected broker not configured error, got %v", err)
	}
	if _, err := client.GetOrderByBrokerID("b-1"); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("GetOrderByBrokerID: expected broker not configured error, got %v", err)
	}
	if _, err := client.ListOrders(); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("ListOrders: expected broker not configured error, got %v", err)
	}
	if _, err := client.ListPositions(); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("ListPositions: expected broker not configured error, got %v", err)
	}
	if _, err := client.GetAccountState(); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("GetAccountState: expected broker not configured error, got %v", err)
	}
	if _, err := client.GetBrokerSnapshot(); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("GetBrokerSnapshot: expected broker not configured error, got %v", err)
	}
	if err := client.ProbeConnectivity(context.Background()); err == nil || !strings.Contains(err.Error(), "broker not configured") {
		t.Fatalf("ProbeConnectivity: expected broker not configured error, got %v", err)
	}
}

func TestAlpacaIdentityEnvironmentExplicit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		http.NotFound(w, r)
	}))
	defer server.Close()

	// A localhost test URL must NOT relabel a paper-configured venue.
	paper := NewAlpacaAdapter("alpaca-test", "key", "secret", true)
	paper.SetBaseURL(server.URL)
	if paper.Environment() != EnvPaper {
		t.Fatalf("Expected EnvPaper for isPaper=true despite localhost URL, got %s", paper.Environment())
	}

	live := NewAlpacaAdapter("alpaca-live", "key", "secret", false)
	live.SetBaseURL(server.URL)
	if live.Environment() != EnvLive {
		t.Fatalf("Expected EnvLive for isPaper=false despite localhost URL, got %s", live.Environment())
	}
}

func TestAlpacaStrictTimestampsRejected(t *testing.T) {
	// Invalid created_at must error rather than fabricate time.Now().
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(alpacaOrderResponse{
			ID:            "bad-created",
			ClientOrderID: "c-created",
			CreatedAt:     "not-a-timestamp",
			UpdatedAt:     "2026-08-21T08:00:01Z",
			Symbol:        "NVDA",
			Qty:           "10",
			FilledQty:     "0",
			Side:          "buy",
			Status:        "accepted",
		})
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	_, err := client.SubmitOrder(&models.OrderIntent{Symbol: "NVDA", Side: models.SideBuy, Qty: 10, ClientOrderID: "c-created"})
	if err == nil || !strings.Contains(err.Error(), "created_at") {
		t.Fatalf("Expected created_at parse error, got %v", err)
	}

	// Invalid updated_at must error too.
	server2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(alpacaOrderResponse{
			ID:            "bad-updated",
			ClientOrderID: "c-updated",
			CreatedAt:     "2026-08-21T08:00:00Z",
			UpdatedAt:     "garbage",
			Symbol:        "NVDA",
			Qty:           "10",
			FilledQty:     "0",
			Side:          "buy",
			Status:        "accepted",
		})
	}))
	defer server2.Close()

	client2 := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client2.SetBaseURL(server2.URL)
	_, err2 := client2.SubmitOrder(&models.OrderIntent{Symbol: "NVDA", Side: models.SideBuy, Qty: 10, ClientOrderID: "c-updated"})
	if err2 == nil || !strings.Contains(err2.Error(), "updated_at") {
		t.Fatalf("Expected updated_at parse error, got %v", err2)
	}
}

func TestAlpacaHealthConnectivityRequiresProbe(t *testing.T) {
	// Unconfigured: configured=false, connected=false, ready=false.
	unconf := NewAlpacaAdapter("alpaca-paper", "", "", true)
	h := unconf.GetHealth()
	if h.Configured || h.Connected || h.Ready {
		t.Fatalf("Unconfigured adapter must not report configured/connected/ready, got %+v", h)
	}
	if h.Environment != EnvPaper {
		t.Fatalf("Expected EnvPaper, got %s", h.Environment)
	}

	// Configured but not yet probed: connected/ready must be false, not inferred from credentials.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Path == "/v2/account" {
			json.NewEncoder(w).Encode(alpacaAccountResponse{Cash: "0", Equity: "0", BuyingPower: "0", Currency: "USD"})
			return
		}
		http.NotFound(w, r)
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	h2 := client.GetHealth()
	if !h2.Configured {
		t.Fatalf("Expected Configured=true, got %+v", h2)
	}
	if h2.Connected || h2.Ready {
		t.Fatalf("Connected/Ready must NOT be inferred from credentials alone, got %+v", h2)
	}

	// After a successful probe, connected/ready become true (cached probe).
	if err := client.ProbeConnectivity(context.Background()); err != nil {
		t.Fatalf("ProbeConnectivity failed: %v", err)
	}
	h3 := client.GetHealth()
	if !h3.Connected || !h3.Ready {
		t.Fatalf("Expected connected/ready after successful probe, got %+v", h3)
	}
	if h3.LastCheckedAt.IsZero() {
		t.Fatalf("Expected LastCheckedAt set after probe")
	}

	// A failed probe flips connectivity off.
	failServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusServiceUnavailable)
	}))
	defer failServer.Close()
	client.SetBaseURL(failServer.URL)
	if err := client.ProbeConnectivity(context.Background()); err == nil {
		t.Fatalf("Expected probe to fail")
	}
	h4 := client.GetHealth()
	if h4.Connected || h4.Ready {
		t.Fatalf("Expected connected/ready false after failed probe, got %+v", h4)
	}
}

func TestAlpacaListOrdersPagination(t *testing.T) {
	requestCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if !strings.HasPrefix(r.URL.Path, "/v2/orders") {
			http.NotFound(w, r)
			return
		}
		requestCount++
		until := r.URL.Query().Get("until")
		if until == "" {
			// Page 1: 500 items (simulated with 500 items where oldest is 2026-08-21T07:00:00Z)
			items := make([]alpacaOrderResponse, 500)
			for i := 0; i < 500; i++ {
				ts := "2026-08-21T08:00:00Z"
				if i == 499 {
					ts = "2026-08-21T07:00:00Z"
				}
				items[i] = alpacaOrderResponse{
					ID:            fmt.Sprintf("page1-ord-%d", i),
					ClientOrderID: fmt.Sprintf("c-page1-%d", i),
					CreatedAt:     ts,
					UpdatedAt:     ts,
					Symbol:        "SPY",
					Qty:           "1",
					Status:        "filled",
				}
			}
			json.NewEncoder(w).Encode(items)
			return
		} else if until == "2026-08-21T07:00:00Z" {
			// Page 2: 5 items (less than limit=500, indicates end)
			items := make([]alpacaOrderResponse, 5)
			for i := 0; i < 5; i++ {
				ts := "2026-08-21T06:00:00Z"
				items[i] = alpacaOrderResponse{
					ID:            fmt.Sprintf("page2-ord-%d", i),
					ClientOrderID: fmt.Sprintf("c-page2-%d", i),
					CreatedAt:     ts,
					UpdatedAt:     ts,
					Symbol:        "SPY",
					Qty:           "1",
					Status:        "filled",
				}
			}
			json.NewEncoder(w).Encode(items)
			return
		}
		json.NewEncoder(w).Encode([]alpacaOrderResponse{})
	}))
	defer server.Close()

	client := NewAlpacaAdapter("alpaca-test", "test-key", "test-secret", true)
	client.SetBaseURL(server.URL)

	orders, err := client.ListOrders()
	if err != nil {
		t.Fatalf("ListOrders failed: %v", err)
	}

	if len(orders) != 505 {
		t.Fatalf("Expected 505 orders across 2 pages, got %d", len(orders))
	}
	if requestCount != 2 {
		t.Fatalf("Expected 2 paginated HTTP requests, got %d", requestCount)
	}
}
