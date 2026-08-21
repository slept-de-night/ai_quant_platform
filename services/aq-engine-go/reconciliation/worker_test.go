package reconciliation

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

type mockEngineAccessor struct {
	mu           sync.Mutex
	isFrozen     bool
	freezeReason string
	frozenBy     string
	snapshot     LocalState
}

func newMockEngineAccessor(cash, equity float64) *mockEngineAccessor {
	return &mockEngineAccessor{
		snapshot: LocalState{
			Orders:    make(map[string]OrderState),
			Positions: make(map[string]PositionState),
			Cash:      cash,
			Equity:    equity,
			Timestamp: time.Now().UTC(),
		},
	}
}

func (m *mockEngineAccessor) ConstructLocalSnapshot() LocalState {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.snapshot
}

func (m *mockEngineAccessor) FreezeWithReason(reason, by, runID string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.isFrozen = true
	m.freezeReason = reason
	m.frozenBy = by
}

func (m *mockEngineAccessor) IsFrozen() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.isFrozen
}

// TestReconciliationWorker_PeriodicExecution verifies periodic background execution
func TestReconciliationWorker_PeriodicExecution(t *testing.T) {
	rec := NewReconciler(0.001, 1.0, 5*time.Minute)
	eng := newMockEngineAccessor(100000.0, 100000.0)

	supplier := func() (string, *BrokerState, error) {
		return "mock-broker", &BrokerState{
			Orders:    make(map[string]OrderState),
			Positions: make(map[string]PositionState),
			Cash:      100000.0,
			Equity:    100000.0,
			Timestamp: time.Now().UTC(),
		}, nil
	}

	worker := NewWorker(rec, eng, supplier, 15*time.Millisecond, 1*time.Second)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	worker.Start(ctx)
	if !worker.IsRunning() {
		t.Fatalf("Expected worker to be running")
	}

	time.Sleep(50 * time.Millisecond)
	worker.Stop()

	if worker.IsRunning() {
		t.Fatalf("Expected worker to be stopped")
	}

	status, isFresh, lastRun, critCount, totCount, activeBroker := rec.GetSummary(time.Now().UTC())
	if status != "CLEAN" || !isFresh || lastRun == nil {
		t.Fatalf("Expected fresh CLEAN summary, got status=%s, fresh=%v", status, isFresh)
	}
	if critCount != 0 || totCount != 0 {
		t.Fatalf("Expected 0 discrepancies, got crit=%d, tot=%d", critCount, totCount)
	}
	if activeBroker != "mock-broker" {
		t.Fatalf("Expected active broker mock-broker, got %s", activeBroker)
	}
}

// TestReconciliationWorker_CriticalDiscrepancyFreezesEngine verifies that critical discrepancies automatically freeze the engine
func TestReconciliationWorker_CriticalDiscrepancyFreezesEngine(t *testing.T) {
	rec := NewReconciler(0.001, 1.0, 5*time.Minute)
	eng := newMockEngineAccessor(100000.0, 100000.0)

	supplier := func() (string, *BrokerState, error) {
		brokerOrders := make(map[string]OrderState)
		brokerOrders["unknown-broker-order-1"] = OrderState{
			ClientOrderID: "unknown-broker-order-1",
			BrokerOrderID: "brk-999",
			Symbol:        "TSLA",
			Side:          "BUY",
			RequestedQty:  100,
			Status:        "FILLED",
			CreatedAt:     time.Now().UTC(),
		}
		return "mock-broker", &BrokerState{
			Orders:    brokerOrders,
			Positions: make(map[string]PositionState),
			Cash:      100000.0,
			Equity:    100000.0,
			Timestamp: time.Now().UTC(),
		}, nil
	}

	worker := NewWorker(rec, eng, supplier, 10*time.Second, 1*time.Second)
	diff, err := worker.RunOnce()
	if err != nil {
		t.Fatalf("RunOnce returned unexpected error: %v", err)
	}

	if diff.TotalCount == 0 || !diff.HasCritical {
		t.Fatalf("Expected critical discrepancy detected, got tot=%d, crit=%v", diff.TotalCount, diff.HasCritical)
	}

	if !eng.IsFrozen() {
		t.Fatalf("Engine MUST be frozen after worker detects critical discrepancy")
	}
}

// TestReconciliationWorker_BrokerUnreachableExceedingMaxAgeFailsClosed verifies fail-closed semantics when broker is unreachable
func TestReconciliationWorker_BrokerUnreachableExceedingMaxAgeFailsClosed(t *testing.T) {
	rec := NewReconciler(0.001, 1.0, 5*time.Minute)
	rec.SetMaxAge(20 * time.Millisecond)

	eng := newMockEngineAccessor(100000.0, 100000.0)

	// Record a prior clean run that took place 50ms ago
	rec.RecordRun("failing-broker-1", Diff{
		TotalCount:  0,
		HasCritical: false,
		GeneratedAt: time.Now().UTC().Add(-50 * time.Millisecond),
	})

	failingSupplier := func() (string, *BrokerState, error) {
		return "failing-broker-1", nil, errors.New("simulated broker connection timeout")
	}

	worker := NewWorker(rec, eng, failingSupplier, 10*time.Second, 20*time.Millisecond)

	_, err := worker.RunOnce()
	if err == nil {
		t.Fatalf("Expected error from unreachable broker")
	}

	if !eng.IsFrozen() {
		t.Fatalf("Engine MUST fail closed and freeze when broker is unreachable for longer than MaxAge")
	}
}
