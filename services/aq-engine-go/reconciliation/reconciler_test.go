package reconciliation

import (
	"testing"
	"time"
)

func TestReconcilerCleanMatch(t *testing.T) {
	now := time.Now().UTC()
	reconciler := NewReconciler(0.001, 1.0, 5*time.Minute)

	local := LocalState{
		Orders: map[string]OrderState{
			"ord-1": {
				ClientOrderID: "ord-1",
				Symbol:        "NVDA",
				RequestedQty:  10,
				FilledQty:     10,
				Status:        "FILLED",
				CreatedAt:     now.Add(-10 * time.Minute),
				UpdatedAt:     now.Add(-5 * time.Minute),
			},
		},
		Positions: map[string]PositionState{
			"NVDA": {Symbol: "NVDA", Qty: 10, MarketValue: 1300.0},
		},
		Cash:      98700.0,
		Equity:    100000.0,
		Timestamp: now,
	}

	broker := BrokerState{
		Orders: map[string]OrderState{
			"ord-1": {
				ClientOrderID: "ord-1",
				BrokerOrderID: "alpaca-1",
				Symbol:        "NVDA",
				RequestedQty:  10,
				FilledQty:     10,
				Status:        "filled",
				CreatedAt:     now.Add(-10 * time.Minute),
				UpdatedAt:     now.Add(-5 * time.Minute),
			},
		},
		Positions: map[string]PositionState{
			"NVDA": {Symbol: "NVDA", Qty: 10, MarketValue: 1300.0},
		},
		Cash:      98700.0,
		Equity:    100000.0,
		Timestamp: now,
	}

	diff := reconciler.Reconcile(local, broker)
	if diff.HasErrors || diff.TotalCount != 0 {
		t.Fatalf("Expected 0 discrepancies, got %d: %v", diff.TotalCount, diff.Discrepancies)
	}
}

func TestReconcilerDiscrepancies(t *testing.T) {
	now := time.Now().UTC()
	reconciler := NewReconciler(0.001, 1.0, 2*time.Minute)

	local := LocalState{
		Orders: map[string]OrderState{
			"ord-local-only": {
				ClientOrderID: "ord-local-only",
				Symbol:        "SPY",
				RequestedQty:  5,
				FilledQty:     0,
				Status:        "SUBMITTED",
				CreatedAt:     now.Add(-5 * time.Minute),
				UpdatedAt:     now.Add(-5 * time.Minute),
			},
			"ord-qty-diff": {
				ClientOrderID: "ord-qty-diff",
				Symbol:        "AAPL",
				RequestedQty:  20,
				FilledQty:     10,
				Status:        "PARTIALLY_FILLED",
				CreatedAt:     now.Add(-5 * time.Minute),
				UpdatedAt:     now.Add(-5 * time.Minute),
			},
		},
		Positions: map[string]PositionState{
			"AAPL": {Symbol: "AAPL", Qty: 10},
		},
		Cash:      100000.0,
		Timestamp: now,
	}

	broker := BrokerState{
		Orders: map[string]OrderState{
			"ord-qty-diff": {
				ClientOrderID: "ord-qty-diff",
				BrokerOrderID: "alpaca-2",
				Symbol:        "AAPL",
				RequestedQty:  20,
				FilledQty:     20, // Broker filled 20, local thought 10
				Status:        "filled",
				CreatedAt:     now.Add(-5 * time.Minute),
				UpdatedAt:     now.Add(-1 * time.Minute),
			},
			"ord-broker-only": {
				ClientOrderID: "ord-broker-only",
				BrokerOrderID: "alpaca-unknown",
				Symbol:        "TSLA",
				RequestedQty:  15,
				FilledQty:     15,
				Status:        "filled",
			},
		},
		Positions: map[string]PositionState{
			"AAPL": {Symbol: "AAPL", Qty: 20}, // Mismatch: 10 vs 20
		},
		Cash:      85000.0, // Mismatch: 100k vs 85k
		Timestamp: now,
	}

	diff := reconciler.Reconcile(local, broker)
	if !diff.HasErrors {
		t.Fatalf("Expected discrepancies, got 0")
	}

	types := make(map[DiscrepancyType]bool)
	for _, d := range diff.Discrepancies {
		types[d.Type] = true
	}

	if !types[DiscrepancyMissingBrokerOrder] {
		t.Errorf("Expected DiscrepancyMissingBrokerOrder")
	}
	if !types[DiscrepancyFillQtyMismatch] {
		t.Errorf("Expected DiscrepancyFillQtyMismatch")
	}
	if !types[DiscrepancyUnknownBrokerOrder] {
		t.Errorf("Expected DiscrepancyUnknownBrokerOrder")
	}
	if !types[DiscrepancyPositionMismatch] {
		t.Errorf("Expected DiscrepancyPositionMismatch")
	}
	if !types[DiscrepancyCashMismatch] {
		t.Errorf("Expected DiscrepancyCashMismatch")
	}

	if !diff.HasCritical {
		t.Errorf("Expected diff.HasCritical to be true due to UnknownBrokerOrder and PositionMismatch")
	}
}

func TestReconcilerSeverityAndCriticalGate(t *testing.T) {
	now := time.Now().UTC()
	reconciler := NewReconciler(0.001, 1.0, 5*time.Minute)

	// Scenario A: Non-critical only (Cash mismatch only)
	localNonCrit := LocalState{
		Orders:    make(map[string]OrderState),
		Positions: make(map[string]PositionState),
		Cash:      100000.0,
		Timestamp: now,
	}
	brokerNonCrit := BrokerState{
		Orders:    make(map[string]OrderState),
		Positions: make(map[string]PositionState),
		Cash:      99000.0, // High severity, but not Critical
		Timestamp: now,
	}
	diffNonCrit := reconciler.Reconcile(localNonCrit, brokerNonCrit)
	if !diffNonCrit.HasErrors {
		t.Fatalf("Expected discrepancies in non-critical diff")
	}
	if diffNonCrit.HasCritical {
		t.Fatalf("Expected HasCritical=false for cash mismatch only")
	}
	if len(diffNonCrit.Discrepancies) != 1 || diffNonCrit.Discrepancies[0].Severity != SeverityHigh {
		t.Fatalf("Expected 1 HIGH severity discrepancy, got %+v", diffNonCrit.Discrepancies)
	}

	// Scenario B: Critical discrepancy (Unknown broker order)
	brokerCrit := BrokerState{
		Orders: map[string]OrderState{
			"ghost-order": {
				ClientOrderID: "ghost-order",
				Symbol:        "NVDA",
				RequestedQty:  10,
				Status:        "filled",
			},
		},
		Positions: make(map[string]PositionState),
		Cash:      100000.0,
		Timestamp: now,
	}
	diffCrit := reconciler.Reconcile(localNonCrit, brokerCrit)
	if !diffCrit.HasCritical {
		t.Fatalf("Expected HasCritical=true for unknown broker order")
	}
	if diffCrit.Discrepancies[0].Severity != SeverityCritical {
		t.Fatalf("Expected SeverityCritical, got %s", diffCrit.Discrepancies[0].Severity)
	}
}

