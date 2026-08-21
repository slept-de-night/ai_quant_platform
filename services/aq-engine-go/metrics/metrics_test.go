package metrics

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestMetricsRegistryCountersAndPrometheus(t *testing.T) {
	r := NewRegistry()

	r.IncOrdersSubmitted()
	r.IncOrdersSubmitted()
	r.IncOrdersRejected()
	r.IncFillsProcessed()
	r.AddReconciliationDiscrepancies(3)
	r.IncEngineFreeze()
	r.RecordLatency(10 * time.Millisecond)
	r.RecordLatency(20 * time.Millisecond)

	s := r.Snapshot()
	if s.OrdersSubmittedTotal != 2 {
		t.Fatalf("Expected OrdersSubmittedTotal=2, got %d", s.OrdersSubmittedTotal)
	}
	if s.OrdersRejectedTotal != 1 {
		t.Fatalf("Expected OrdersRejectedTotal=1, got %d", s.OrdersRejectedTotal)
	}
	if s.FillsProcessedTotal != 1 {
		t.Fatalf("Expected FillsProcessedTotal=1, got %d", s.FillsProcessedTotal)
	}
	if s.ReconciliationDiscrepanciesTotal != 3 {
		t.Fatalf("Expected ReconciliationDiscrepanciesTotal=3, got %d", s.ReconciliationDiscrepanciesTotal)
	}
	if s.EngineFreezeTotal != 1 {
		t.Fatalf("Expected EngineFreezeTotal=1, got %d", s.EngineFreezeTotal)
	}
	if s.RequestCount != 2 {
		t.Fatalf("Expected RequestCount=2, got %d", s.RequestCount)
	}
	if s.AvgLatencyMs < 14.0 || s.AvgLatencyMs > 16.0 {
		t.Fatalf("Expected AvgLatencyMs ~15.0, got %f", s.AvgLatencyMs)
	}

	prom := r.PrometheusFormat()
	if !strings.Contains(prom, "aq_engine_orders_submitted_total 2") {
		t.Fatalf("Prometheus output missing orders_submitted_total: %s", prom)
	}
	if !strings.Contains(prom, "aq_engine_reconciliation_discrepancies_total 3") {
		t.Fatalf("Prometheus output missing discrepancies: %s", prom)
	}
}

func TestMetricsMiddleware(t *testing.T) {
	r := NewRegistry()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /test", func(w http.ResponseWriter, req *http.Request) {
		time.Sleep(5 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ok"))
	})

	handler := r.Middleware(mux)
	req := httptest.NewRequest("GET", "/test", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("Expected 200, got %d", rec.Code)
	}

	s := r.Snapshot()
	if s.RequestCount != 1 {
		t.Fatalf("Expected 1 recorded request, got %d", s.RequestCount)
	}
	if s.AvgLatencyMs <= 0.0 {
		t.Fatalf("Expected non-zero latency, got %f", s.AvgLatencyMs)
	}
}
