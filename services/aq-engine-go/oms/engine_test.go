package oms

import (
	"testing"

	"aq-engine-go/models"
)

func TestEngineEmergencyFreeze(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)

	order := &models.OrderIntent{
		Symbol:         "NVDA",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 130.0,
		Notional:       1300.0,
		ClientOrderID:  "ord-1",
		TraceID:        "trace-12345",
	}

	// 1. Normal order should pass
	d := engine.EvaluateRisk(order)
	if !d.Approved {
		t.Fatalf("Expected order to be approved, got reasons: %v", d.Reasons)
	}

	// 2. Duplicate order should be rejected
	d2 := engine.EvaluateRisk(order)
	if d2.Approved {
		t.Fatalf("Expected duplicate order to be rejected")
	}

	// 3. Freeze engine
	engine.Freeze()
	if !engine.IsFrozen() {
		t.Fatalf("Expected engine to be frozen")
	}

	order2 := &models.OrderIntent{
		Symbol:         "SPY",
		Side:           models.SideBuy,
		Qty:            5,
		ReferencePrice: 500.0,
		Notional:       2500.0,
		ClientOrderID:  "ord-2",
		TraceID:        "trace-67890",
	}

	d3 := engine.EvaluateRisk(order2)
	if d3.Approved {
		t.Fatalf("Expected order to be rejected when engine is frozen")
	}

	// 4. Unfreeze and verify order succeeds
	engine.Unfreeze()
	if engine.IsFrozen() {
		t.Fatalf("Expected engine to be unfrozen")
	}

	d4 := engine.EvaluateRisk(order2)
	if !d4.Approved {
		t.Fatalf("Expected order to be approved after unfreeze, got reasons: %v", d4.Reasons)
	}

	// 5. Verify order history
	history := engine.GetOrderHistory()
	if len(history) != 2 {
		t.Fatalf("Expected 2 orders in history, got %d", len(history))
	}
	if history[0].TraceID != "trace-12345" {
		t.Fatalf("Expected TraceID trace-12345, got %s", history[0].TraceID)
	}
}
