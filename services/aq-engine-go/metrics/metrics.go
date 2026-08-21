package metrics

import (
	"fmt"
	"net/http"
	"strings"
	"sync/atomic"
	"time"
)

type MetricsRegistry struct {
	ordersSubmittedTotal            atomic.Uint64
	ordersRejectedTotal             atomic.Uint64
	fillsProcessedTotal             atomic.Uint64
	reconciliationDiscrepanciesTotal atomic.Uint64
	engineFreezeTotal               atomic.Uint64
	requestCount                    atomic.Uint64
	totalLatencyNs                  atomic.Uint64
	startTime                       time.Time
}

var DefaultRegistry = NewRegistry()

func NewRegistry() *MetricsRegistry {
	return &MetricsRegistry{
		startTime: time.Now().UTC(),
	}
}

func (m *MetricsRegistry) IncOrdersSubmitted() {
	m.ordersSubmittedTotal.Add(1)
}

func (m *MetricsRegistry) IncOrdersRejected() {
	m.ordersRejectedTotal.Add(1)
}

func (m *MetricsRegistry) IncFillsProcessed() {
	m.fillsProcessedTotal.Add(1)
}

func (m *MetricsRegistry) AddReconciliationDiscrepancies(count uint64) {
	m.reconciliationDiscrepanciesTotal.Add(count)
}

func (m *MetricsRegistry) IncEngineFreeze() {
	m.engineFreezeTotal.Add(1)
}

func (m *MetricsRegistry) RecordLatency(d time.Duration) {
	m.requestCount.Add(1)
	m.totalLatencyNs.Add(uint64(d.Nanoseconds()))
}

type MetricsSnapshot struct {
	UptimeSeconds                   float64 `json:"uptime_seconds"`
	OrdersSubmittedTotal            uint64  `json:"orders_submitted_total"`
	OrdersRejectedTotal             uint64  `json:"orders_rejected_total"`
	FillsProcessedTotal             uint64  `json:"fills_processed_total"`
	ReconciliationDiscrepanciesTotal uint64  `json:"reconciliation_discrepancies_total"`
	EngineFreezeTotal               uint64  `json:"engine_freeze_total"`
	RequestCount                    uint64  `json:"request_count"`
	AvgLatencyMs                    float64 `json:"avg_latency_ms"`
}

func (m *MetricsRegistry) Snapshot() MetricsSnapshot {
	reqCount := m.requestCount.Load()
	totalNs := m.totalLatencyNs.Load()
	avgMs := 0.0
	if reqCount > 0 {
		avgMs = float64(totalNs) / float64(reqCount) / 1e6
	}

	return MetricsSnapshot{
		UptimeSeconds:                   time.Since(m.startTime).Seconds(),
		OrdersSubmittedTotal:            m.ordersSubmittedTotal.Load(),
		OrdersRejectedTotal:             m.ordersRejectedTotal.Load(),
		FillsProcessedTotal:             m.fillsProcessedTotal.Load(),
		ReconciliationDiscrepanciesTotal: m.reconciliationDiscrepanciesTotal.Load(),
		EngineFreezeTotal:               m.engineFreezeTotal.Load(),
		RequestCount:                    reqCount,
		AvgLatencyMs:                    avgMs,
	}
}

func (m *MetricsRegistry) PrometheusFormat() string {
	s := m.Snapshot()
	var b strings.Builder
	b.WriteString("# HELP aq_engine_uptime_seconds Process uptime in seconds\n")
	b.WriteString("# TYPE aq_engine_uptime_seconds gauge\n")
	b.WriteString(fmt.Sprintf("aq_engine_uptime_seconds %.2f\n", s.UptimeSeconds))

	b.WriteString("# HELP aq_engine_orders_submitted_total Total orders submitted to brokers\n")
	b.WriteString("# TYPE aq_engine_orders_submitted_total counter\n")
	b.WriteString(fmt.Sprintf("aq_engine_orders_submitted_total %d\n", s.OrdersSubmittedTotal))

	b.WriteString("# HELP aq_engine_orders_rejected_total Total orders rejected by risk checks\n")
	b.WriteString("# TYPE aq_engine_orders_rejected_total counter\n")
	b.WriteString(fmt.Sprintf("aq_engine_orders_rejected_total %d\n", s.OrdersRejectedTotal))

	b.WriteString("# HELP aq_engine_fills_processed_total Total fills recorded in ledger\n")
	b.WriteString("# TYPE aq_engine_fills_processed_total counter\n")
	b.WriteString(fmt.Sprintf("aq_engine_fills_processed_total %d\n", s.FillsProcessedTotal))

	b.WriteString("# HELP aq_engine_reconciliation_discrepancies_total Discrepancies detected\n")
	b.WriteString("# TYPE aq_engine_reconciliation_discrepancies_total counter\n")
	b.WriteString(fmt.Sprintf("aq_engine_reconciliation_discrepancies_total %d\n", s.ReconciliationDiscrepanciesTotal))

	b.WriteString("# HELP aq_engine_freeze_total Total times engine was frozen\n")
	b.WriteString("# TYPE aq_engine_freeze_total counter\n")
	b.WriteString(fmt.Sprintf("aq_engine_freeze_total %d\n", s.EngineFreezeTotal))

	b.WriteString("# HELP aq_engine_request_latency_ms_avg Average HTTP request latency in ms\n")
	b.WriteString("# TYPE aq_engine_request_latency_ms_avg gauge\n")
	b.WriteString(fmt.Sprintf("aq_engine_request_latency_ms_avg %.4f\n", s.AvgLatencyMs))

	return b.String()
}

// Middleware records HTTP request duration and count.
func (m *MetricsRegistry) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		m.RecordLatency(time.Since(start))
	})
}
