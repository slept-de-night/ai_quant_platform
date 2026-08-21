package oms

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"aq-engine-go/models"
)

func TestJournalReplayCleanRecovery(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "oms_journal_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	journalPath := filepath.Join(tempDir, "journal.jsonl")

	// 1. First Engine session: write orders and fills
	journal1, err := NewJournal(journalPath)
	if err != nil {
		t.Fatalf("Failed to create journal: %v", err)
	}

	cfg := models.DefaultRiskConfig()
	engine1 := NewEngine(200000.0, cfg)
	engine1.SetJournal(journal1)

	ord := &models.OrderIntent{
		Symbol:         "AAPL",
		Side:           models.SideBuy,
		Qty:            50,
		RequestedQty:   50.0,
		ReferencePrice: 150.0,
		Notional:       7500.0,
		ClientOrderID:  "j-ord-1",
		TraceID:        "trace-1",
	}

	resOrd, dec := engine1.ReserveOrder(ord)
	if !dec.Approved || resOrd == nil {
		t.Fatalf("ReserveOrder failed: %v", dec.Reasons)
	}

	engine1.UpdateOrderStatusAndBrokerID("j-ord-1", models.OrderStatusAcknowledged, "broker-alp-1")

	fill := models.Fill{
		FillID:        "j-fill-1",
		BrokerOrderID: "broker-alp-1",
		ClientOrderID: "j-ord-1",
		Symbol:        "AAPL",
		Side:          models.SideBuy,
		Qty:           50.0,
		Price:         150.0,
		Timestamp:     time.Now().UTC(),
	}
	_, err = engine1.ApplyFill(fill)
	if err != nil {
		t.Fatalf("ApplyFill failed: %v", err)
	}

	// Close journal 1
	journal1.Close()

	// 2. Second Engine session: fresh instance, replay journal
	journal2, err := NewJournal(journalPath)
	if err != nil {
		t.Fatalf("Failed to reopen journal: %v", err)
	}
	defer journal2.Close()

	engine2 := NewEngine(200000.0, cfg)
	count, err := journal2.Replay(engine2)
	if err != nil {
		t.Fatalf("Replay failed: %v", err)
	}

	if count != 3 { // Reserved/Submitting -> Acknowledged -> FillRecorded
		t.Fatalf("Expected 3 replayed events, got %d", count)
	}

	// Verify exact state recovery
	recOrd, exists := engine2.GetOrderByClientID("j-ord-1")
	if !exists || recOrd.Status != models.OrderStatusFilled || recOrd.FilledQty != 50 {
		t.Fatalf("Order state recovery failed: exists=%v, ord=%+v", exists, recOrd)
	}

	pos, ok := engine2.GetPosition("AAPL")
	if !ok || pos.Qty != 50.0 || pos.CostBasis != 7500.0 {
		t.Fatalf("Position state recovery failed: ok=%v, pos=%+v", ok, pos)
	}

	p := engine2.GetPortfolio("AAPL")
	if p.Cash != 192500.0 || p.CurrentSymbolQty != 50.0 {
		t.Fatalf("Portfolio state recovery failed: cash=%.2f, qty=%.2f", p.Cash, p.CurrentSymbolQty)
	}
}

func TestJournalCorruptLineHandling(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "oms_journal_corrupt_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	journalPath := filepath.Join(tempDir, "corrupt.jsonl")

	// Write valid line then corrupt line
	content := `{"event_id":"evt-1","sequence":1,"type":"ENGINE_UNFROZEN","timestamp":"2026-08-21T08:00:00Z"}` + "\n" +
		`{corrupt-json-not-valid` + "\n"
	if err := os.WriteFile(journalPath, []byte(content), 0644); err != nil {
		t.Fatalf("Failed to write corrupt journal: %v", err)
	}

	journal, err := NewJournal(journalPath)
	if err != nil {
		t.Fatalf("Failed to open journal: %v", err)
	}
	defer journal.Close()

	engine := NewEngine(100000.0, models.DefaultRiskConfig())
	_, err = journal.Replay(engine)
	if err == nil {
		t.Fatalf("Expected replay error on corrupted line, got nil")
	}

	// Corrupt journal must freeze the engine for safety
	if !engine.IsFrozen() {
		t.Fatalf("Expected engine to be FROZEN on corrupt journal replay")
	}
}

func TestJournalSequenceDiscontinuity(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "oms_journal_seq_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	journalPath := filepath.Join(tempDir, "seq.jsonl")

	// Sequence 1 followed by Sequence 3 (missing 2)
	content := `{"event_id":"evt-1","sequence":1,"type":"ENGINE_UNFROZEN","timestamp":"2026-08-21T08:00:00Z"}` + "\n" +
		`{"event_id":"evt-3","sequence":3,"type":"ENGINE_FROZEN","timestamp":"2026-08-21T08:00:01Z"}` + "\n"
	if err := os.WriteFile(journalPath, []byte(content), 0644); err != nil {
		t.Fatalf("Failed to write seq journal: %v", err)
	}

	journal, err := NewJournal(journalPath)
	if err != nil {
		t.Fatalf("Failed to open journal: %v", err)
	}
	defer journal.Close()

	engine := NewEngine(100000.0, models.DefaultRiskConfig())
	_, err = journal.Replay(engine)
	if err == nil {
		t.Fatalf("Expected error on sequence discontinuity, got nil")
	}

	if !engine.IsFrozen() {
		t.Fatalf("Expected engine to be FROZEN on sequence discontinuity")
	}
}
