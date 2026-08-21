package broker

import (
	"encoding/json"
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
