package webull

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"aq-engine-go/models"
)

type mockOMSConsumer struct {
	mu           sync.Mutex
	statusCalls  []struct {
		ClientOrderID string
		Status        models.OrderStatus
	}
	fillCalls    []models.Fill
}

func (m *mockOMSConsumer) ApplyFill(fill models.Fill) (*models.Position, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.fillCalls = append(m.fillCalls, fill)
	return &models.Position{
		Symbol:      fill.Symbol,
		Qty:         fill.Qty,
		MarketValue: fill.Qty * fill.Price,
		CostBasis:   fill.Qty * fill.Price,
	}, nil
}

func (m *mockOMSConsumer) UpdateOrderStatus(clientOrderID string, status models.OrderStatus, reasons ...string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.statusCalls = append(m.statusCalls, struct {
		ClientOrderID string
		Status        models.OrderStatus
	}{ClientOrderID: clientOrderID, Status: status})
	return nil
}

// TestStreamConsumer_ProcessOrderStatusUpdate verifies status mapping and dispatch to OMS.
func TestStreamConsumer_ProcessOrderStatusUpdate(t *testing.T) {
	oms := &mockOMSConsumer{}
	consumer := NewStreamConsumer(oms, nil, 30*time.Second)

	msg := &StreamMessage{
		Type:          EventTypeOrderStatus,
		ClientOrderID: "order_test_123",
		OrderID:       "wb_ord_99",
		Symbol:        "AAPL",
		Status:        "FILLED",
	}

	err := consumer.ProcessMessage(msg)
	if err != nil {
		t.Fatalf("ProcessMessage failed: %v", err)
	}

	oms.mu.Lock()
	defer oms.mu.Unlock()

	if len(oms.statusCalls) != 1 {
		t.Fatalf("Expected 1 status update call, got %d", len(oms.statusCalls))
	}
	if oms.statusCalls[0].ClientOrderID != "order_test_123" || oms.statusCalls[0].Status != models.OrderStatusFilled {
		t.Fatalf("Status call mismatch: %+v", oms.statusCalls[0])
	}
}

// TestStreamConsumer_ProcessOrderFill verifies fill extraction and dispatch to OMS.
func TestStreamConsumer_ProcessOrderFill(t *testing.T) {
	oms := &mockOMSConsumer{}
	consumer := NewStreamConsumer(oms, nil, 30*time.Second)

	msg := &StreamMessage{
		Type:          EventTypeOrderFill,
		ClientOrderID: "cli_ord_456",
		OrderID:       "wb_ord_77",
		Symbol:        "NVDA",
		Side:          "BUY",
		Quantity:      25.0,
		Price:         480.50,
		FillID:        "fill_wb_001",
		Timestamp:     time.Date(2026, 8, 21, 14, 0, 0, 0, time.UTC),
	}

	err := consumer.ProcessMessage(msg)
	if err != nil {
		t.Fatalf("ProcessMessage failed: %v", err)
	}

	oms.mu.Lock()
	defer oms.mu.Unlock()

	if len(oms.fillCalls) != 1 {
		t.Fatalf("Expected 1 fill call, got %d", len(oms.fillCalls))
	}

	fill := oms.fillCalls[0]
	if fill.ClientOrderID != "cli_ord_456" || fill.Symbol != "NVDA" || fill.Qty != 25.0 || fill.Price != 480.50 || fill.Side != models.SideBuy {
		t.Fatalf("Fill mismatch: %+v", fill)
	}
}

// TestStreamConsumer_WatchdogSilenceTriggersFallbackPolling verifies fallback polling on stream silence.
func TestStreamConsumer_WatchdogSilenceTriggersFallbackPolling(t *testing.T) {
	var fallbackCalls int32

	poller := func(ctx context.Context) error {
		atomic.AddInt32(&fallbackCalls, 1)
		return nil
	}

	oms := &mockOMSConsumer{}
	// Configure short 20ms timeout for testing
	consumer := NewStreamConsumer(oms, poller, 20*time.Millisecond)

	// Simulate initial state where last heartbeat was 50ms ago
	consumer.mu.Lock()
	consumer.lastHeartbeat = time.Now().UTC().Add(-50 * time.Millisecond)
	consumer.mu.Unlock()

	consumer.checkWatchdog(context.Background())

	if atomic.LoadInt32(&fallbackCalls) != 1 {
		t.Fatalf("Expected fallback poller to be called on silence, got %d calls", atomic.LoadInt32(&fallbackCalls))
	}
	if consumer.FallbackTriggerCount() != 1 {
		t.Fatalf("Expected FallbackTriggerCount 1, got %d", consumer.FallbackTriggerCount())
	}
}

// TestParseStreamPayload verifies raw JSON parsing.
func TestParseStreamPayload(t *testing.T) {
	raw := []byte(`{
		"type": "ORDER_FILL",
		"account_id": "acc_001",
		"order_id": "wb_9988",
		"client_order_id": "c_9988",
		"symbol": "TSLA",
		"side": "SELL",
		"quantity": 10.0,
		"price": 230.50,
		"fill_id": "f_1"
	}`)

	msg, err := ParseStreamPayload(raw)
	if err != nil {
		t.Fatalf("ParseStreamPayload failed: %v", err)
	}

	if msg.Type != EventTypeOrderFill || msg.Symbol != "TSLA" || msg.Price != 230.50 || msg.Quantity != 10.0 {
		t.Fatalf("Parsed message mismatch: %+v", msg)
	}
}
