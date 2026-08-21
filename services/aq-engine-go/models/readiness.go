package models

import "time"

type TradingReadiness string

const (
	TradingReady    TradingReadiness = "READY"
	TradingNotReady TradingReadiness = "NOT_READY"
	TradingFrozen   TradingReadiness = "FROZEN"
	TradingUnknown  TradingReadiness = "UNKNOWN"
)

type ReconciliationSummary struct {
	Status        string     `json:"status"` // "UNKNOWN", "CLEAN", "MISMATCH", "FAILED", "STALE", "NOT_RUN"
	LastRunAt     *time.Time `json:"last_run_at,omitempty"`
	CriticalCount int        `json:"critical_count"`
	TotalCount    int        `json:"total_count"`
	IsFresh       bool       `json:"is_fresh"`
	MaxAgeSeconds int        `json:"max_age_seconds"`
	BrokerName    string     `json:"broker_name,omitempty"`
}

type MarketDataSummary struct {
	Status    string     `json:"status"` // "LIVE", "DEMO", "UNAVAILABLE", "STALE"
	UpdatedAt *time.Time `json:"updated_at,omitempty"`
	TickCount int        `json:"tick_count"`
}

type ReadinessReport struct {
	Process          string                `json:"process"`
	TradingReady     bool                  `json:"trading_ready"`
	TradingReadiness TradingReadiness      `json:"trading_readiness"`
	ExecutionMode    string                `json:"execution_mode"`
	ActiveBroker     string                `json:"active_broker"`
	BrokerConfigured bool                  `json:"broker_configured"`
	BrokerConnected  bool                  `json:"broker_connected"`
	BrokerReady      bool                  `json:"broker_ready"`
	JournalReady     bool                  `json:"journal_ready"`
	Reconciliation   ReconciliationSummary `json:"reconciliation"`
	IsFrozen         bool                  `json:"is_frozen"`
	FreezeReason     string                `json:"freeze_reason,omitempty"`
	FrozenAt         *time.Time            `json:"frozen_at,omitempty"`
	FrozenBy         string                `json:"frozen_by,omitempty"`
	MarketData       MarketDataSummary     `json:"market_data"`
	BlockingReasons  []string              `json:"blocking_reasons"`
	Timestamp        time.Time             `json:"timestamp"`
}
