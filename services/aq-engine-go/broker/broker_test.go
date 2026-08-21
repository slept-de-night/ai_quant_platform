package broker

import (
	"testing"

	"aq-engine-go/models"
)

func TestBrokerStatusNormalization(t *testing.T) {
	tests := []struct {
		raw      string
		expected BrokerOrderStatus
	}{
		{"new", BrokerOrderStatusAcknowledged},
		{"accepted", BrokerOrderStatusAcknowledged},
		{"held", BrokerOrderStatusAcknowledged},
		{"pending", BrokerOrderStatusAcknowledged},
		{"submitting", BrokerOrderStatusSubmitting},
		{"pending_new", BrokerOrderStatusSubmitting},
		{"open", BrokerOrderStatusSubmitting},
		{"partially_filled", BrokerOrderStatusPartiallyFilled},
		{"partiallyfilled", BrokerOrderStatusPartiallyFilled},
		{"filled", BrokerOrderStatusFilled},
		{"executed", BrokerOrderStatusFilled},
		{"complete", BrokerOrderStatusFilled},
		{"pending_cancel", BrokerOrderStatusCancelPending},
		{"cancel_pending", BrokerOrderStatusCancelPending},
		{"canceled", BrokerOrderStatusCanceled},
		{"cancelled", BrokerOrderStatusCanceled},
		{"done_for_day", BrokerOrderStatusCanceled},
		{"expired", BrokerOrderStatusExpired},
		{"rejected", BrokerOrderStatusRejected},
		{"declined", BrokerOrderStatusRejected},
		{"failed", BrokerOrderStatusSubmitFailed},
		{"submit_failed", BrokerOrderStatusSubmitFailed},
		{"unknown_state", BrokerOrderStatusAcknowledged}, // safe default
	}

	for _, tc := range tests {
		got := NormalizeBrokerStatus(tc.raw)
		if got != tc.expected {
			t.Errorf("NormalizeBrokerStatus(%q) = %q, expected %q", tc.raw, got, tc.expected)
		}
	}
}

func TestPaperAdapterOrderLifecycle(t *testing.T) {
	paper := NewPaperAdapter("test-paper", 50000.0)

	order := &models.OrderIntent{
		Symbol:         "NVDA",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 130.0,
		ClientOrderID:  "ord-test-1",
	}

	bo, err := paper.SubmitOrder(order)
	if err != nil {
		t.Fatalf("SubmitOrder failed: %v", err)
	}

	if bo.Status != BrokerOrderStatusFilled || bo.FilledQty != 10 {
		t.Fatalf("Expected filled order with qty 10, got status=%s, filled=%d", bo.Status, bo.FilledQty)
	}
	if bo.RequestedQty != 10.0 {
		t.Fatalf("Expected RequestedQty 10.0, got %.2f", bo.RequestedQty)
	}
	if bo.AverageFillPrice != 130.0 {
		t.Fatalf("Expected AverageFillPrice 130.0, got %.2f", bo.AverageFillPrice)
	}
	if bo.BrokerOrderID == "" {
		t.Fatalf("Expected non-empty BrokerOrderID")
	}

	acct, err := paper.GetAccountState()
	if err != nil {
		t.Fatalf("GetAccountState failed: %v", err)
	}
	expectedCash := 50000.0 - (10 * 130.0)
	if acct.Cash != expectedCash {
		t.Fatalf("Expected cash $%.2f, got $%.2f", expectedCash, acct.Cash)
	}

	positions, err := paper.ListPositions()
	if err != nil || len(positions) != 1 {
		t.Fatalf("Expected 1 position, got %d", len(positions))
	}
	if positions[0].Symbol != "NVDA" || positions[0].Qty != 10 {
		t.Fatalf("Expected 10 NVDA, got %v", positions[0])
	}

	// Test CancelOrder normalization
	cancelOrder := &models.OrderIntent{
		Symbol:         "AAPL",
		Side:           models.SideBuy,
		Qty:            5,
		ReferencePrice: 200.0,
		ClientOrderID:  "ord-cancel-1",
	}
	_, _ = paper.SubmitOrder(cancelOrder)
	if err := paper.CancelOrder("ord-cancel-1"); err != nil {
		t.Fatalf("CancelOrder failed: %v", err)
	}
	cancelledBo, err := paper.GetOrder("ord-cancel-1")
	if err != nil {
		t.Fatalf("GetOrder failed: %v", err)
	}
	if cancelledBo.Status != BrokerOrderStatusCanceled {
		t.Fatalf("Expected status CANCELED, got %s", cancelledBo.Status)
	}
}

func TestBrokerRegistrySwitching(t *testing.T) {
	reg := NewRegistry()

	paper := NewPaperAdapter("paper-sim", 100000.0)
	webull := NewWebullAdapter("webull-main", "", "", "", true)
	alpaca := NewAlpacaAdapter("alpaca-paper", "", "", true)

	reg.Register(paper)
	reg.Register(webull)
	reg.Register(alpaca)

	active, err := reg.GetActive()
	if err != nil || active.Name() != "paper-sim" {
		t.Fatalf("Expected default active adapter to be paper-sim, got %v", active)
	}

	// Switch to Webull
	if err := reg.SetActive("webull-main"); err != nil {
		t.Fatalf("Failed to switch to Webull: %v", err)
	}

	activeWebull, err := reg.GetActive()
	if err != nil || activeWebull.Kind() != BrokerKindWebull {
		t.Fatalf("Expected active adapter to be Webull, got %v", activeWebull)
	}

	// List all brokers
	list := reg.List()
	if len(list) != 3 {
		t.Fatalf("Expected 3 registered brokers, got %d", len(list))
	}
}
