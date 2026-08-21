package oms

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"aq-engine-go/models"
)

type JournalEventType string

const (
	EventOrderReserved     JournalEventType = "ORDER_RESERVED"
	EventOrderSubmitting   JournalEventType = "ORDER_SUBMITTING"
	EventOrderAcknowledged JournalEventType = "ORDER_ACKNOWLEDGED"
	EventOrderSubmitFailed JournalEventType = "ORDER_SUBMIT_FAILED"
	EventFillRecorded      JournalEventType = "FILL_RECORDED"
	EventOrderCanceled     JournalEventType = "ORDER_CANCELED"
	EventEngineFrozen      JournalEventType = "ENGINE_FROZEN"
	EventEngineUnfrozen    JournalEventType = "ENGINE_UNFROZEN"
)

type JournalEvent struct {
	SchemaVersion       string              `json:"schema_version,omitempty"`
	EventID             string              `json:"event_id"`
	Sequence            int64               `json:"sequence"`
	Type                JournalEventType    `json:"type"`
	Timestamp           time.Time           `json:"timestamp"`
	Order               *models.OrderIntent `json:"order,omitempty"`
	Fill                *models.Fill        `json:"fill,omitempty"`
	ClientOrderID       string              `json:"client_order_id,omitempty"`
	BrokerOrderID       string              `json:"broker_order_id,omitempty"`
	Reason              string              `json:"reason,omitempty"`
	RequestedBy         string              `json:"requested_by,omitempty"`
	ReconciliationRunID string              `json:"reconciliation_run_id,omitempty"`
	TraceID             string              `json:"trace_id,omitempty"`
}

type Journal struct {
	path           string
	file           *os.File
	mu             sync.Mutex
	seq            int64
	injectWriteErr error
	injectSyncErr  error
}

func (j *Journal) SetInjectWriteError(err error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.injectWriteErr = err
}

func (j *Journal) SetInjectSyncError(err error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.injectSyncErr = err
}

func NewJournal(path string) (*Journal, error) {
	if path == "" {
		return &Journal{}, nil // in-memory dummy mode
	}

	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create journal directory: %w", err)
	}

	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR|os.O_APPEND, 0644)
	if err != nil {
		return nil, fmt.Errorf("failed to open journal file %s: %w", path, err)
	}

	return &Journal{
		path: path,
		file: f,
	}, nil
}

func (j *Journal) Close() error {
	j.mu.Lock()
	defer j.mu.Unlock()
	if j.file != nil {
		return j.file.Close()
	}
	return nil
}

func (j *Journal) RecordEvent(evtType JournalEventType, order *models.OrderIntent, fill *models.Fill, clientOrderID, brokerOrderID, reason string) error {
	return j.RecordEventWithContext(evtType, order, fill, clientOrderID, brokerOrderID, reason, "", "", "")
}

func (j *Journal) RecordEventWithContext(evtType JournalEventType, order *models.OrderIntent, fill *models.Fill, clientOrderID, brokerOrderID, reason, requestedBy, reconciliationRunID, traceID string) error {
	if j == nil || j.file == nil {
		return nil
	}

	j.mu.Lock()
	defer j.mu.Unlock()

	if j.injectWriteErr != nil {
		return fmt.Errorf("injected disk write error: %w", j.injectWriteErr)
	}

	j.seq++
	now := time.Now().UTC()
	evt := JournalEvent{
		SchemaVersion:       "1.0",
		EventID:             fmt.Sprintf("evt-%d-%d", now.UnixNano(), j.seq),
		Sequence:            j.seq,
		Type:                evtType,
		Timestamp:           now,
		Order:               order,
		Fill:                fill,
		ClientOrderID:       clientOrderID,
		BrokerOrderID:       brokerOrderID,
		Reason:              reason,
		RequestedBy:         requestedBy,
		ReconciliationRunID: reconciliationRunID,
		TraceID:             traceID,
	}

	bytes, err := json.Marshal(evt)
	if err != nil {
		return fmt.Errorf("failed to marshal journal event: %w", err)
	}

	if _, err := j.file.Write(append(bytes, '\n')); err != nil {
		return fmt.Errorf("failed to write journal event to disk: %w", err)
	}

	if j.injectSyncErr != nil {
		return fmt.Errorf("injected fsync error: %w", j.injectSyncErr)
	}

	return j.file.Sync() // Durable fsync
}

// Replay loads events in order and rebuilds the full Engine in-memory state.
func (j *Journal) Replay(engine *Engine) (int64, error) {
	if j == nil || j.path == "" {
		return 0, nil
	}

	j.mu.Lock()
	defer j.mu.Unlock()

	f, err := os.Open(j.path)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, fmt.Errorf("failed to open journal for replay: %w", err)
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	var count int64 = 0
	var lastSeq int64 = 0

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var evt JournalEvent
		if err := json.Unmarshal(line, &evt); err != nil {
			// Corrupt line detected: freeze engine for safety and return error
			engine.Freeze()
			return count, fmt.Errorf("corrupt journal line detected at event count %d: %w", count, err)
		}

		if evt.Sequence > 0 && evt.Sequence != lastSeq+1 && lastSeq > 0 {
			engine.Freeze()
			return count, fmt.Errorf("journal sequence discontinuity: expected %d, got %d", lastSeq+1, evt.Sequence)
		}
		if evt.Sequence > 0 {
			lastSeq = evt.Sequence
		}

		// Replay mutation into engine without re-journaling
		engine.replayEvent(evt)
		count++
	}

	if err := scanner.Err(); err != nil {
		engine.Freeze()
		return count, fmt.Errorf("error reading journal during replay: %w", err)
	}

	j.seq = lastSeq
	return count, nil
}
