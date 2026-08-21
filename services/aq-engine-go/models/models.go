package models

import "time"

type Side string

const (
	SideBuy  Side = "buy"
	SideSell Side = "sell"
	SideHold Side = "hold"
)

type OrderStatus string

const (
	OrderStatusPending      OrderStatus = "PENDING"
	OrderStatusApproved     OrderStatus = "APPROVED"
	OrderStatusRejected     OrderStatus = "REJECTED"
	OrderStatusSubmitting   OrderStatus = "SUBMITTING"
	OrderStatusSubmitted    OrderStatus = "SUBMITTED"
	OrderStatusAcknowledged OrderStatus = "ACKNOWLEDGED"
	OrderStatusFilled       OrderStatus = "FILLED"
	OrderStatusCancelled    OrderStatus = "CANCELLED"
	OrderStatusSubmitFailed OrderStatus = "SUBMIT_FAILED"
)

type OrderIntent struct {
	Symbol          string      `json:"symbol"`
	StrategyName    string      `json:"strategy_name"`
	Side            Side        `json:"side"`
	Qty             int         `json:"qty"`
	ReferencePrice  float64     `json:"reference_price"`
	Notional        float64     `json:"notional"`
	ClientOrderID   string      `json:"client_order_id"`
	TraceID         string      `json:"trace_id,omitempty"`
	RunID           string      `json:"run_id,omitempty"`
	DecisionID      string      `json:"decision_id,omitempty"`
	SnapshotID      string      `json:"snapshot_id,omitempty"`
	StrategyID      string      `json:"strategy_id,omitempty"`
	StrategyVersion string      `json:"strategy_version,omitempty"`
	DatasetVersion  string      `json:"dataset_version,omitempty"`
	Status          OrderStatus `json:"status,omitempty"`
	Reason          string      `json:"reason"`
	CreatedAt       time.Time   `json:"created_at"`
}


type PortfolioState struct {
	Equity                float64 `json:"equity"`
	Cash                  float64 `json:"cash"`
	GrossExposure         float64 `json:"gross_exposure"`
	DailyPnL              float64 `json:"daily_pnl"`
	PeakEquity            float64 `json:"peak_equity"`
	CurrentSymbolExposure float64 `json:"current_symbol_exposure"`
	CurrentSymbolQty      float64 `json:"current_symbol_qty"`
	OrdersToday           int     `json:"orders_today"`
	IsFrozen              bool    `json:"is_frozen"`
}

type RiskDecision struct {
	Approved bool         `json:"approved"`
	Order    *OrderIntent `json:"order,omitempty"`
	Reasons  []string     `json:"reasons"`
	TraceID  string       `json:"trace_id,omitempty"`
}

type RiskConfig struct {
	MaxPositionPct          float64 `json:"max_position_pct"`
	MaxGrossExposurePct     float64 `json:"max_gross_exposure_pct"`
	MinCashReservePct       float64 `json:"min_cash_reserve_pct"`
	MaxDailyLossPct         float64 `json:"max_daily_loss_pct"`
	MaxDrawdownPct          float64 `json:"max_drawdown_pct"`
	MaxOrdersPerDay         int     `json:"max_orders_per_day"`
	MinOrderNotional        float64 `json:"min_order_notional"`
	MaxTickStalenessSeconds float64 `json:"max_tick_staleness_seconds"`
}

func DefaultRiskConfig() RiskConfig {
	return RiskConfig{
		MaxPositionPct:          0.08,
		MaxGrossExposurePct:     0.60,
		MinCashReservePct:       0.10,
		MaxDailyLossPct:         0.02,
		MaxDrawdownPct:          0.10,
		MaxOrdersPerDay:         8,
		MinOrderNotional:        50.0,
		MaxTickStalenessSeconds: 60.0,
	}
}

type MarketTick struct {
	Symbol    string    `json:"symbol"`
	Price     float64   `json:"price"`
	Volume    float64   `json:"volume"`
	Timestamp time.Time `json:"timestamp"`
}

