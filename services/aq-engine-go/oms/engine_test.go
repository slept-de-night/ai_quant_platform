package oms

import (
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

// mockBroker is a test spy implementing broker.BrokerAdapter
type mockBroker struct {
	mu          sync.Mutex
	submitCalls int
	shouldFail  bool
	failErr     error
	orders      map[string]broker.BrokerOrder
}

func newMockBroker(shouldFail bool, failErr error) *mockBroker {
	if failErr == nil {
		failErr = errors.New("simulated broker connection failure")
	}
	return &mockBroker{
		shouldFail: shouldFail,
		failErr:    failErr,
		orders:     make(map[string]broker.BrokerOrder),
	}
}

func (m *mockBroker) Name() string                     { return "mock-broker" }
func (m *mockBroker) Kind() broker.BrokerKind          { return broker.BrokerKindPaper }
func (m *mockBroker) Environment() broker.Environment  { return broker.EnvSimulation }
func (m *mockBroker) IsConfigured() bool               { return true }
func (m *mockBroker) CancelOrder(id string) error      { return nil }
func (m *mockBroker) GetOrder(id string) (*broker.BrokerOrder, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if ord, ok := m.orders[id]; ok {
		return &ord, nil
	}
	return nil, fmt.Errorf("order not found: %s", id)
}
func (m *mockBroker) ListOrders() ([]broker.BrokerOrder, error)       { return nil, nil }
func (m *mockBroker) ListPositions() ([]broker.BrokerPosition, error) { return nil, nil }
func (m *mockBroker) GetAccountState() (*broker.AccountState, error) {
	return &broker.AccountState{Cash: 100000, Equity: 100000}, nil
}
func (m *mockBroker) GetHealth() broker.Health {
	return broker.Health{Ready: true, Connected: true, Name: "mock-broker"}
}
func (m *mockBroker) GetBrokerSnapshot() (*reconciliation.BrokerState, error) {
	return &reconciliation.BrokerState{
		Orders:    make(map[string]reconciliation.OrderState),
		Positions: make(map[string]reconciliation.PositionState),
		Cash:      100000,
		Equity:    100000,
		Timestamp: time.Now().UTC(),
	}, nil
}

func (m *mockBroker) SubmitOrder(order *models.OrderIntent) (*broker.BrokerOrder, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.submitCalls++

	if m.shouldFail {
		return nil, m.failErr
	}

	bo := broker.BrokerOrder{
		ID:            fmt.Sprintf("mock-%d", m.submitCalls),
		ClientOrderID: order.ClientOrderID,
		Symbol:        order.Symbol,
		Side:          string(order.Side),
		Qty:           order.Qty,
		FilledQty:     order.Qty,
		Status:        "filled",
		CreatedAt:     time.Now().UTC(),
		UpdatedAt:     time.Now().UTC(),
	}
	m.orders[order.ClientOrderID] = bo
	return &bo, nil
}

func (m *mockBroker) GetSubmitCalls() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.submitCalls
}

// 1. Test: risk check does not change dailyOrders
func TestCheckRiskDoesNotChangeDailyOrders(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)

	order := &models.OrderIntent{
		Symbol:         "NVDA",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 130.0,
		Notional:       1300.0,
		ClientOrderID:  "pure-risk-1",
		TraceID:        "trace-pure-1",
	}

	// Initial dailyOrders must be 0
	p0 := engine.GetPortfolio("")
	if p0.OrdersToday != 0 {
		t.Fatalf("Expected initial OrdersToday=0, got %d", p0.OrdersToday)
	}

	// Perform multiple CheckRisk calls
	for i := 0; i < 5; i++ {
		d := engine.CheckRisk(order)
		if !d.Approved {
			t.Fatalf("Iteration %d: expected CheckRisk to approve, got reasons: %v", i, d.Reasons)
		}
	}

	// Verify dailyOrders is still 0
	p1 := engine.GetPortfolio("")
	if p1.OrdersToday != 0 {
		t.Fatalf("CheckRisk mutated dailyOrders: expected 0, got %d", p1.OrdersToday)
	}
}

// 2. Test: risk check does not consume client_order_id
func TestCheckRiskDoesNotConsumeClientOrderID(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)

	order := &models.OrderIntent{
		Symbol:         "MSFT",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 400.0,
		Notional:       4000.0,
		ClientOrderID:  "idempotency-key-1",
		TraceID:        "trace-idem-1",
	}

	// Check risk
	d1 := engine.CheckRisk(order)
	if !d1.Approved {
		t.Fatalf("Expected CheckRisk to approve, got: %v", d1.Reasons)
	}

	// Check risk again with identical client_order_id — MUST NOT be rejected as duplicate
	d2 := engine.CheckRisk(order)
	if !d2.Approved {
		t.Fatalf("CheckRisk consumed client_order_id! Second check rejected: %v", d2.Reasons)
	}

	// Verify orderHistory is empty
	history := engine.GetOrderHistory()
	if len(history) != 0 {
		t.Fatalf("CheckRisk mutated orderHistory: expected 0 orders, found %d", len(history))
	}
}

// 3. Test: risk check followed by submit succeeds
func TestCheckRiskFollowedBySubmitSucceeds(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)
	mb := newMockBroker(false, nil)

	order := &models.OrderIntent{
		Symbol:         "AAPL",
		Side:           models.SideBuy,
		Qty:            15,
		ReferencePrice: 220.0,
		Notional:       3300.0,
		ClientOrderID:  "order-flow-1",
		TraceID:        "trace-flow-1",
	}

	// 1. Pure risk check
	decision := engine.CheckRisk(order)
	if !decision.Approved {
		t.Fatalf("Pure risk check failed: %v", decision.Reasons)
	}

	// 2. Submit order with the same client_order_id
	bo, submitDec, err := engine.Submit(order, mb)
	if err != nil {
		t.Fatalf("Submit failed unexpectedly: %v", err)
	}
	if !submitDec.Approved {
		t.Fatalf("Expected submit decision approved, got reasons: %v", submitDec.Reasons)
	}
	if bo == nil {
		t.Fatalf("Expected non-nil broker order response")
	}

	// Verify order is recorded as ACKNOWLEDGED
	history := engine.GetOrderHistory()
	if len(history) != 1 {
		t.Fatalf("Expected 1 order in history, got %d", len(history))
	}
	if history[0].Status != models.OrderStatusAcknowledged {
		t.Fatalf("Expected status %s, got %s", models.OrderStatusAcknowledged, history[0].Status)
	}
	if history[0].ClientOrderID != "order-flow-1" {
		t.Fatalf("Expected ClientOrderID 'order-flow-1', got %s", history[0].ClientOrderID)
	}
}

// 4. Test: successful submit records exactly one local order
func TestSuccessfulSubmitRecordsExactlyOneLocalOrder(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)
	mb := newMockBroker(false, nil)

	order := &models.OrderIntent{
		Symbol:         "GOOGL",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 175.0,
		Notional:       1750.0,
		ClientOrderID:  "single-record-1",
		TraceID:        "trace-single-1",
	}

	_, _, err := engine.Submit(order, mb)
	if err != nil {
		t.Fatalf("Submit error: %v", err)
	}

	history := engine.GetOrderHistory()
	if len(history) != 1 {
		t.Fatalf("Expected exactly 1 order in history, got %d", len(history))
	}

	p := engine.GetPortfolio("")
	if p.OrdersToday != 1 {
		t.Fatalf("Expected OrdersToday=1, got %d", p.OrdersToday)
	}
}

// 5. Test: duplicate submit never invokes broker twice
func TestDuplicateSubmitNeverInvokesBrokerTwice(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)
	mb := newMockBroker(false, nil)

	order := &models.OrderIntent{
		Symbol:         "SPY",
		Side:           models.SideBuy,
		Qty:            5,
		ReferencePrice: 500.0,
		Notional:       2500.0,
		ClientOrderID:  "dup-check-1",
		TraceID:        "trace-dup-1",
	}

	// First submit: succeeds
	_, dec1, err1 := engine.Submit(order, mb)
	if err1 != nil || !dec1.Approved {
		t.Fatalf("First submit failed: %v", err1)
	}
	if mb.GetSubmitCalls() != 1 {
		t.Fatalf("Expected 1 broker call, got %d", mb.GetSubmitCalls())
	}

	// Repeated submit with identical client_order_id: must be rejected before broker
	_, dec2, err2 := engine.Submit(order, mb)
	if err2 == nil || dec2.Approved {
		t.Fatalf("Expected duplicate submit to be rejected, got approved")
	}

	// Broker MUST NOT have been invoked a second time
	if mb.GetSubmitCalls() != 1 {
		t.Fatalf("Duplicate submit invoked broker twice! Calls: %d", mb.GetSubmitCalls())
	}

	// Order history must still have exactly 1 order
	if len(engine.GetOrderHistory()) != 1 {
		t.Fatalf("Expected 1 order in history, got %d", len(engine.GetOrderHistory()))
	}
}

// 6. Test: broker failure records SUBMIT_FAILED
func TestBrokerFailureRecordsSubmitFailed(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)
	mb := newMockBroker(true, errors.New("upstream broker timeout 504"))

	order := &models.OrderIntent{
		Symbol:         "AMD",
		Side:           models.SideBuy,
		Qty:            20,
		ReferencePrice: 150.0,
		Notional:       3000.0,
		ClientOrderID:  "fail-check-1",
		TraceID:        "trace-fail-1",
	}

	_, _, err := engine.Submit(order, mb)
	if err == nil {
		t.Fatalf("Expected submit to fail due to broker error")
	}

	// Order must remain visible in history with SUBMIT_FAILED
	history := engine.GetOrderHistory()
	if len(history) != 1 {
		t.Fatalf("Expected 1 order in history after failure, got %d", len(history))
	}
	failedOrd := history[0]
	if failedOrd.Status != models.OrderStatusSubmitFailed {
		t.Fatalf("Expected status %s, got %s", models.OrderStatusSubmitFailed, failedOrd.Status)
	}
	if failedOrd.Reason == "" {
		t.Fatalf("Expected failure reason to be recorded on order")
	}
}

// 7. Test: kill switch blocks submission
func TestKillSwitchBlocksSubmission(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)
	mb := newMockBroker(false, nil)

	// Freeze engine
	engine.Freeze()
	if !engine.IsFrozen() {
		t.Fatalf("Expected engine to be frozen")
	}

	order := &models.OrderIntent{
		Symbol:         "TSLA",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 200.0,
		Notional:       2000.0,
		ClientOrderID:  "freeze-order-1",
		TraceID:        "trace-freeze-1",
	}

	// Submission must be blocked
	_, dec, err := engine.Submit(order, mb)
	if err == nil || dec.Approved {
		t.Fatalf("Expected submission to be blocked while frozen")
	}

	// Broker should not be contacted
	if mb.GetSubmitCalls() != 0 {
		t.Fatalf("Broker was contacted while frozen: %d calls", mb.GetSubmitCalls())
	}

	// Unfreeze and verify submission works
	engine.Unfreeze()
	if engine.IsFrozen() {
		t.Fatalf("Expected engine to be unfrozen")
	}

	_, dec2, err2 := engine.Submit(order, mb)
	if err2 != nil || !dec2.Approved {
		t.Fatalf("Expected submission to succeed after unfreeze: %v", err2)
	}
	if mb.GetSubmitCalls() != 1 {
		t.Fatalf("Expected 1 broker call after unfreeze, got %d", mb.GetSubmitCalls())
	}
}

// 8. Test: read-only reconciliation/risk operations remain available while frozen
func TestReadOnlyReconciliationAndRiskOperationsAvailableWhileFrozen(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)

	// Freeze engine
	engine.Freeze()

	// 1. Portfolio query works cleanly
	p := engine.GetPortfolio("SPY")
	if !p.IsFrozen {
		t.Fatalf("Expected portfolio.IsFrozen to be true")
	}
	if p.Equity != 100000.0 {
		t.Fatalf("Expected equity 100000.0, got %.2f", p.Equity)
	}

	// 2. Order history query works cleanly
	history := engine.GetOrderHistory()
	if history == nil {
		t.Fatalf("Expected non-nil order history slice")
	}

	// 3. CheckRisk runs cleanly without panic (returns rejection reason for freeze)
	testOrd := &models.OrderIntent{
		Symbol:         "SPY",
		Side:           models.SideBuy,
		Qty:            1,
		ReferencePrice: 500.0,
		Notional:       500.0,
		ClientOrderID:  "frozen-chk-1",
	}
	dec := engine.CheckRisk(testOrd)
	if dec.Approved {
		t.Fatalf("Expected CheckRisk to report unapproved while frozen")
	}
	if len(dec.Reasons) == 0 {
		t.Fatalf("Expected rejection reason for frozen engine")
	}

	// 4. Reconciliation runs cleanly without panic
	reconciler := reconciliation.NewReconciler(0.001, 1.0, 5*time.Minute)
	localState := reconciliation.LocalState{
		Orders:    make(map[string]reconciliation.OrderState),
		Positions: make(map[string]reconciliation.PositionState),
		Cash:      p.Cash,
		Equity:    p.Equity,
		Timestamp: time.Now().UTC(),
	}
	brokerState := reconciliation.BrokerState{
		Orders:    make(map[string]reconciliation.OrderState),
		Positions: make(map[string]reconciliation.PositionState),
		Cash:      p.Cash,
		Equity:    p.Equity,
		Timestamp: time.Now().UTC(),
	}

	diff := reconciler.Reconcile(localState, brokerState)
	if diff.HasErrors {
		t.Fatalf("Reconciliation failed unexpectedly: %v", diff.Discrepancies)
	}
}

// 9. Test: concurrent duplicate submissions invoke broker exactly once
func TestConcurrentDuplicateSubmissionsInvokeBrokerExactlyOnce(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)
	mb := newMockBroker(false, nil)

	order := &models.OrderIntent{
		Symbol:         "QQQ",
		Side:           models.SideBuy,
		Qty:            5,
		ReferencePrice: 450.0,
		Notional:       2250.0,
		ClientOrderID:  "concurrent-idem-1",
		TraceID:        "trace-concurrent-1",
	}

	const goroutines = 20
	var wg sync.WaitGroup
	var mu sync.Mutex
	successCount := 0
	failCount := 0

	for i := 0; i < goroutines; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, dec, err := engine.Submit(order, mb)
			mu.Lock()
			defer mu.Unlock()
			if err == nil && dec.Approved {
				successCount++
			} else {
				failCount++
			}
		}()
	}

	wg.Wait()

	// Exactly 1 submission must succeed
	if successCount != 1 {
		t.Fatalf("Expected exactly 1 successful submission, got %d", successCount)
	}
	if failCount != goroutines-1 {
		t.Fatalf("Expected %d failed duplicate submissions, got %d", goroutines-1, failCount)
	}

	// Broker must be called exactly once
	if mb.GetSubmitCalls() != 1 {
		t.Fatalf("Expected broker to be called exactly 1 time, got %d", mb.GetSubmitCalls())
	}

	// Engine history must contain exactly 1 order
	history := engine.GetOrderHistory()
	if len(history) != 1 {
		t.Fatalf("Expected 1 order in history, got %d", len(history))
	}
	if history[0].Status != models.OrderStatusAcknowledged {
		t.Fatalf("Expected status %s, got %s", models.OrderStatusAcknowledged, history[0].Status)
	}
}

// 10. Test: successful submit stores broker order ID in order history
func TestSuccessfulSubmitStoresBrokerOrderID(t *testing.T) {
	cfg := models.DefaultRiskConfig()
	engine := NewEngine(100000.0, cfg)
	mb := newMockBroker(false, nil)

	order := &models.OrderIntent{
		Symbol:         "META",
		Side:           models.SideBuy,
		Qty:            8,
		ReferencePrice: 500.0,
		Notional:       4000.0,
		ClientOrderID:  "broker-id-test-1",
		TraceID:        "trace-broker-id-1",
	}

	bo, dec, err := engine.Submit(order, mb)
	if err != nil || !dec.Approved {
		t.Fatalf("Expected submit to succeed, got: %v", err)
	}
	if bo == nil || bo.ID == "" {
		t.Fatalf("Expected valid broker order response with ID")
	}

	// Check that engine history records the broker order ID
	ord, exists := engine.GetOrderByClientID("broker-id-test-1")
	if !exists {
		t.Fatalf("Order not found in history")
	}
	if ord.BrokerOrderID != bo.ID {
		t.Fatalf("Expected BrokerOrderID '%s', got '%s'", bo.ID, ord.BrokerOrderID)
	}
	if ord.Status != models.OrderStatusAcknowledged {
		t.Fatalf("Expected status ACKNOWLEDGED, got %s", ord.Status)
	}
}

