package reconciliation

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"aq-engine-go/metrics"
)

// EngineStateAccessor exposes OMS snapshot and freeze interfaces to the reconciliation worker.
type EngineStateAccessor interface {
	ConstructLocalSnapshot() LocalState
	FreezeWithReason(reason, by, runID string)
	IsFrozen() bool
}

// BrokerSnapshotSupplier returns the active broker's name and snapshot.
type BrokerSnapshotSupplier func() (brokerName string, snapshot *BrokerState, err error)

// Worker executes continuous periodic reconciliation between local OMS and the active broker.
type Worker struct {
	mu           sync.Mutex
	reconciler   *Reconciler
	engine       EngineStateAccessor
	supplier     BrokerSnapshotSupplier
	interval     time.Duration
	maxAge       time.Duration
	cancelFunc   context.CancelFunc
	running      bool
	lastRunError error
}

// NewWorker constructs a background reconciliation worker.
func NewWorker(reconciler *Reconciler, engine EngineStateAccessor, supplier BrokerSnapshotSupplier, interval, maxAge time.Duration) *Worker {
	if interval <= 0 {
		interval = 30 * time.Second
	}
	if maxAge <= 0 {
		maxAge = 300 * time.Second
	}
	return &Worker{
		reconciler: reconciler,
		engine:     engine,
		supplier:   supplier,
		interval:   interval,
		maxAge:     maxAge,
	}
}

// Start launches the background reconciliation loop.
func (w *Worker) Start(ctx context.Context) {
	w.mu.Lock()
	if w.running {
		w.mu.Unlock()
		return
	}
	workerCtx, cancel := context.WithCancel(ctx)
	w.cancelFunc = cancel
	w.running = true
	w.mu.Unlock()

	go w.runLoop(workerCtx)
}

// Stop terminates the background reconciliation worker.
func (w *Worker) Stop() {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.running && w.cancelFunc != nil {
		w.cancelFunc()
		w.running = false
	}
}

// IsRunning reports whether the worker background goroutine is active.
func (w *Worker) IsRunning() bool {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.running
}

// RunOnce executes a single deterministic reconciliation pass.
func (w *Worker) RunOnce() (Diff, error) {
	if w.supplier == nil {
		err := fmt.Errorf("no broker snapshot supplier configured")
		w.mu.Lock()
		w.lastRunError = err
		w.mu.Unlock()
		return Diff{}, err
	}

	brokerName, brokerSnapshot, err := w.supplier()
	if err != nil || brokerSnapshot == nil {
		w.mu.Lock()
		w.lastRunError = err
		w.mu.Unlock()

		// Check if broker unreachability exceeds max age -> fail closed by freezing OMS
		now := time.Now().UTC()
		_, isFresh, lastRun, _, _, _ := w.reconciler.GetSummary(now)
		if !isFresh && lastRun != nil && now.Sub(*lastRun) > w.maxAge {
			w.engine.FreezeWithReason(fmt.Sprintf("broker %s unreachable for >%.0fs (%v); failing closed", brokerName, w.maxAge.Seconds(), err), "reconciliation_worker", "")
			log.Printf("[RECONCILIATION WORKER ALERT] Broker %s unreachable for >%.0fs. Failed closed and froze engine.", brokerName, w.maxAge.Seconds())
		}
		return Diff{}, fmt.Errorf("failed to fetch snapshot from broker %s: %w", brokerName, err)
	}

	localSnapshot := w.engine.ConstructLocalSnapshot()
	diff := w.reconciler.Reconcile(localSnapshot, *brokerSnapshot)
	w.reconciler.RecordRun(brokerName, diff)
	metrics.DefaultRegistry.AddReconciliationDiscrepancies(uint64(diff.TotalCount))

	if diff.HasCritical {
		w.engine.FreezeWithReason(fmt.Sprintf("critical reconciliation discrepancy detected by background worker (%d discrepancies)", diff.TotalCount), "reconciliation_worker", "")
		log.Printf("[RECONCILIATION WORKER ALERT] Critical discrepancy detected on broker %s (%d total). Engine FROZEN.", brokerName, diff.TotalCount)
	}

	w.mu.Lock()
	w.lastRunError = nil
	w.mu.Unlock()

	return diff, nil
}

func (w *Worker) runLoop(ctx context.Context) {
	ticker := time.NewTicker(w.interval)
	defer ticker.Stop()

	// Initial immediate pass
	_, _ = w.RunOnce()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			_, _ = w.RunOnce()
		}
	}
}
