package broker

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"aq-engine-go/models"
)

// runBrokerContractSuite runs standardized behavioral conformance tests against any BrokerAdapter implementation.
func runBrokerContractSuite(t *testing.T, b BrokerAdapter) {
	t.Run("AdapterMetadata", func(t *testing.T) {
		if b.Name() == "" {
			t.Errorf("Expected non-empty adapter Name()")
		}
		if b.Kind() == "" {
			t.Errorf("Expected non-empty adapter Kind()")
		}
		if b.Environment() == "" {
			t.Errorf("Expected non-empty adapter Environment()")
		}
		health := b.GetHealth()
		// Configured is a local property of credentials; Connected/Ready must
		// NOT be inferred from configured alone (that would claim connectivity
		// without an actual probe).
		if health.Configured != b.IsConfigured() {
			t.Errorf("Expected adapter health Configured=%v (matching IsConfigured), got %+v", b.IsConfigured(), health)
		}
		if health.Connected && !b.IsConfigured() {
			t.Errorf("Expected Connected=false for an unconfigured adapter, got %+v", health)
		}
		if health.Ready && !b.IsConfigured() {
			t.Errorf("Expected Ready=false for an unconfigured adapter, got %+v", health)
		}
	})

	t.Run("SubmitOrderNormalization", func(t *testing.T) {
		order := &models.OrderIntent{
			Symbol:         "MSFT",
			Side:           models.SideBuy,
			Qty:            10,
			ReferencePrice: 400.0,
			Notional:       4000.0,
			ClientOrderID:  "contract-ord-1",
			CreatedAt:      time.Now().UTC(),
		}

		bo, err := b.SubmitOrder(order)
		if err != nil {
			t.Fatalf("SubmitOrder failed on %s: %v", b.Name(), err)
		}
		if bo == nil {
			t.Fatalf("SubmitOrder returned nil BrokerOrder on %s", b.Name())
		}
		if bo.BrokerOrderID == "" && bo.ID == "" {
			t.Errorf("Expected non-empty BrokerOrderID on %s", b.Name())
		}
		if bo.ClientOrderID != "contract-ord-1" {
			t.Errorf("Expected ClientOrderID 'contract-ord-1', got '%s'", bo.ClientOrderID)
		}
		if bo.Symbol != "MSFT" {
			t.Errorf("Expected Symbol 'MSFT', got '%s'", bo.Symbol)
		}
		if bo.RequestedQty != 10.0 {
			t.Errorf("Expected RequestedQty 10.0, got %.2f", bo.RequestedQty)
		}
		if bo.Status == "" {
			t.Errorf("Expected non-empty normalized BrokerOrderStatus")
		}
		// Invariant: Status must be one of the canonical normalized constants
		switch bo.Status {
		case BrokerOrderStatusAcknowledged, BrokerOrderStatusSubmitting, BrokerOrderStatusPartiallyFilled, BrokerOrderStatusFilled, BrokerOrderStatusCancelPending, BrokerOrderStatusCanceled, BrokerOrderStatusExpired, BrokerOrderStatusRejected, BrokerOrderStatusSubmitFailed:
			// Valid normalized status
		default:
			t.Errorf("Invalid or raw status leaked: %s", bo.Status)
		}
	})

	t.Run("CancelOrderNormalization", func(t *testing.T) {
		err := b.CancelOrder("contract-ord-1")
		if err != nil {
			t.Logf("CancelOrder on %s returned: %v (acceptable for mock adapters)", b.Name(), err)
		}
	})

	t.Run("ListPositionsNormalization", func(t *testing.T) {
		positions, err := b.ListPositions()
		if err != nil {
			t.Fatalf("ListPositions failed on %s: %v", b.Name(), err)
		}
		if positions == nil {
			t.Errorf("Expected non-nil positions slice on %s", b.Name())
		}
		for _, pos := range positions {
			if pos.Symbol == "" {
				t.Errorf("Position missing symbol on %s: %+v", b.Name(), pos)
			}
		}
	})

	t.Run("GetAccountStateNormalization", func(t *testing.T) {
		acct, err := b.GetAccountState()
		if err != nil {
			t.Fatalf("GetAccountState failed on %s: %v", b.Name(), err)
		}
		if acct == nil {
			t.Fatalf("GetAccountState returned nil on %s", b.Name())
		}
		if acct.Equity <= 0 {
			t.Errorf("Expected positive Equity on %s, got %.2f", b.Name(), acct.Equity)
		}
		if acct.Currency == "" {
			t.Errorf("Expected non-empty Currency on %s", b.Name())
		}
	})

	t.Run("GetBrokerSnapshotNormalization", func(t *testing.T) {
		snap, err := b.GetBrokerSnapshot()
		if err != nil {
			t.Fatalf("GetBrokerSnapshot failed on %s: %v", b.Name(), err)
		}
		if snap == nil {
			t.Fatalf("GetBrokerSnapshot returned nil on %s", b.Name())
		}
		if snap.Timestamp.IsZero() {
			t.Errorf("Expected non-zero timestamp in BrokerSnapshot on %s", b.Name())
		}
		if snap.Orders == nil {
			t.Errorf("Expected non-nil Orders map in BrokerSnapshot on %s", b.Name())
		}
		if snap.Positions == nil {
			t.Errorf("Expected non-nil Positions map in BrokerSnapshot on %s", b.Name())
		}
	})
}

func TestBrokerContractSuite_PaperAdapter(t *testing.T) {
	paper := NewPaperAdapter("paper-sim-conformance", 100000.0)
	runBrokerContractSuite(t, paper)
}

func TestBrokerContractSuite_AlpacaAdapterOffline(t *testing.T) {
	// Set up mock HTTP server for Alpaca
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v2/orders":
			if r.Method == "POST" {
				json.NewEncoder(w).Encode(alpacaOrderResponse{
					ID:            "alpaca-contract-ord-1",
					ClientOrderID: "contract-ord-1",
					CreatedAt:     "2026-08-21T08:00:00Z",
					UpdatedAt:     "2026-08-21T08:00:01Z",
					Symbol:        "MSFT",
					Qty:           "10",
					FilledQty:     "0",
					Side:          "buy",
					Status:        "accepted",
				})
			} else {
				json.NewEncoder(w).Encode([]alpacaOrderResponse{})
			}
		case "/v2/orders:by_client_order_id":
			if r.Method == "DELETE" {
				w.WriteHeader(http.StatusNoContent)
			} else {
				json.NewEncoder(w).Encode(alpacaOrderResponse{
					ID:            "alpaca-contract-ord-1",
					ClientOrderID: "contract-ord-1",
					CreatedAt:     "2026-08-21T08:00:00Z",
					UpdatedAt:     "2026-08-21T08:00:01Z",
					Symbol:        "MSFT",
					Qty:           "10",
					FilledQty:     "0",
					Side:          "buy",
					Status:        "canceled",
				})
			}
		case "/v2/positions":
			json.NewEncoder(w).Encode([]alpacaPositionResponse{
				{Symbol: "MSFT", Qty: "10", MarketValue: "4000.00", CostBasis: "4000.00"},
			})
		case "/v2/account":
			json.NewEncoder(w).Encode(alpacaAccountResponse{
				Cash:        "96000.00",
				Equity:      "100000.00",
				BuyingPower: "192000.00",
				Currency:    "USD",
				Status:      "ACTIVE",
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	alpaca := NewAlpacaAdapter("alpaca-contract-test", "key", "secret", true)
	alpaca.SetBaseURL(server.URL)

	runBrokerContractSuite(t, alpaca)
}

func TestBrokerContractSuite_WebullQuarantine(t *testing.T) {
	// 1. Unconfigured Webull must fail closed with ErrBrokerNotConfigured and never masquerade as paper
	webullUnconfigured := NewWebullAdapter("webull-unconfigured", "", "", "", true)
	if webullUnconfigured.IsConfigured() {
		t.Fatalf("Unconfigured adapter reported IsConfigured=true")
	}

	hUnconf := webullUnconfigured.GetHealth()
	if hUnconf.Ready || hUnconf.Connected || hUnconf.Configured {
		t.Fatalf("Unconfigured health must be false for Ready, Connected, Configured; got %+v", hUnconf)
	}

	if _, err := webullUnconfigured.SubmitOrder(&models.OrderIntent{Symbol: "NVDA", Side: models.SideBuy, Qty: 10}); err != ErrBrokerNotConfigured {
		t.Fatalf("Expected ErrBrokerNotConfigured on SubmitOrder, got %v", err)
	}
	if err := webullUnconfigured.CancelOrder("client-1"); err != ErrBrokerNotConfigured {
		t.Fatalf("Expected ErrBrokerNotConfigured on CancelOrder, got %v", err)
	}
	if _, err := webullUnconfigured.GetOrder("client-1"); err != ErrBrokerNotConfigured {
		t.Fatalf("Expected ErrBrokerNotConfigured on GetOrder, got %v", err)
	}
	if _, err := webullUnconfigured.ListOrders(); err != ErrBrokerNotConfigured {
		t.Fatalf("Expected ErrBrokerNotConfigured on ListOrders, got %v", err)
	}
	if _, err := webullUnconfigured.ListPositions(); err != ErrBrokerNotConfigured {
		t.Fatalf("Expected ErrBrokerNotConfigured on ListPositions, got %v", err)
	}
	if _, err := webullUnconfigured.GetAccountState(); err != ErrBrokerNotConfigured {
		t.Fatalf("Expected ErrBrokerNotConfigured on GetAccountState, got %v", err)
	}
	if _, err := webullUnconfigured.GetBrokerSnapshot(); err != ErrBrokerNotConfigured {
		t.Fatalf("Expected ErrBrokerNotConfigured on GetBrokerSnapshot, got %v", err)
	}

	// 2. Configured Webull in Phase W0 must report Ready=false, Connected=false, and refuse fake execution
	webullConfigured := NewWebullAdapter("webull-configured", "test_app_key", "test_app_secret", "test_account", true)
	if !webullConfigured.IsConfigured() {
		t.Fatalf("Configured adapter reported IsConfigured=false")
	}
	hConf := webullConfigured.GetHealth()
	if hConf.Ready || hConf.Connected {
		t.Fatalf("Quarantined adapter must report Ready=false, Connected=false; got %+v", hConf)
	}
	if !hConf.Configured {
		t.Fatalf("Configured adapter must report Configured=true")
	}
	if hConf.Capabilities == nil || hConf.Capabilities.SubmitOrder {
		t.Fatalf("Quarantined capabilities must be all false")
	}

	if _, err := webullConfigured.SubmitOrder(&models.OrderIntent{Symbol: "NVDA", Side: models.SideBuy, Qty: 10}); err == nil {
		t.Fatalf("Quarantined adapter must reject order placement")
	}
	if _, err := webullConfigured.GetAccountState(); err == nil {
		t.Fatalf("Quarantined adapter must reject fake account state")
	}
	if _, err := webullConfigured.GetBrokerSnapshot(); err == nil {
		t.Fatalf("Quarantined adapter must reject fake broker snapshot")
	}
}

func TestAlpacaStrictPayloadParsingErrors(t *testing.T) {
	// Test malformed position quantities
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v2/positions":
			json.NewEncoder(w).Encode([]alpacaPositionResponse{
				{Symbol: "AAPL", Qty: "not-a-number", MarketValue: "100.0", CostBasis: "100.0"},
			})
		case "/v2/account":
			json.NewEncoder(w).Encode(alpacaAccountResponse{
				Cash: "corrupted_cash",
			})
		}
	}))
	defer server.Close()

	alpaca := NewAlpacaAdapter("alpaca-strict-test", "key", "secret", true)
	alpaca.SetBaseURL(server.URL)

	_, err := alpaca.ListPositions()
	if err == nil {
		t.Fatalf("Expected error when parsing non-numeric position quantity, got nil")
	}

	_, err = alpaca.GetAccountState()
	if err == nil {
		t.Fatalf("Expected error when parsing non-numeric account cash, got nil")
	}
}
