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
	OrderStatusCreated                OrderStatus = "CREATED"
	OrderStatusRiskApproved           OrderStatus = "RISK_APPROVED"
	OrderStatusPending                OrderStatus = "PENDING"
	OrderStatusApproved               OrderStatus = "APPROVED"
	OrderStatusRejected               OrderStatus = "REJECTED"
	OrderStatusSubmitting             OrderStatus = "SUBMITTING"
	OrderStatusSubmitted              OrderStatus = "SUBMITTED"
	OrderStatusAcknowledged           OrderStatus = "ACKNOWLEDGED"
	OrderStatusPartiallyFilled        OrderStatus = "PARTIALLY_FILLED"
	OrderStatusFilled                 OrderStatus = "FILLED"
	OrderStatusCancelPending          OrderStatus = "CANCEL_PENDING"
	OrderStatusCancelled              OrderStatus = "CANCELLED"
	OrderStatusSubmitFailed           OrderStatus = "SUBMIT_FAILED"
	OrderStatusExpired                OrderStatus = "EXPIRED"
	OrderStatusReconciliationRequired OrderStatus = "RECONCILIATION_REQUIRED"
)

type OrderIntent struct {
	Symbol           string      `json:"symbol"`
	StrategyName     string      `json:"strategy_name"`
	Side             Side        `json:"side"`
	Qty              int         `json:"qty"`
	RequestedQty     float64     `json:"requested_qty,omitempty"`
	FilledQty        int         `json:"filled_qty"`
	FilledQtyFloat   float64     `json:"filled_qty_float,omitempty"`
	AverageFillPrice float64     `json:"average_fill_price,omitempty"`
	ReferencePrice   float64     `json:"reference_price"`
	Notional         float64     `json:"notional"`
	ClientOrderID    string      `json:"client_order_id"`
	BrokerOrderID    string      `json:"broker_order_id,omitempty"`
	TraceID          string      `json:"trace_id,omitempty"`
	RunID            string      `json:"run_id,omitempty"`
	DecisionID       string      `json:"decision_id,omitempty"`
	SnapshotID       string      `json:"snapshot_id,omitempty"`
	StrategyID       string      `json:"strategy_id,omitempty"`
	StrategyVersion  string      `json:"strategy_version,omitempty"`
	DatasetVersion   string      `json:"dataset_version,omitempty"`
	Status           OrderStatus `json:"status,omitempty"`
	Reason           string      `json:"reason"`
	CreatedAt        time.Time   `json:"created_at"`
	UpdatedAt        time.Time   `json:"updated_at,omitempty"`
}

type Fill struct {
	FillID        string    `json:"fill_id"`
	BrokerOrderID string    `json:"broker_order_id"`
	ClientOrderID string    `json:"client_order_id"`
	Symbol        string    `json:"symbol"`
	Side          Side      `json:"side"`
	Qty           float64   `json:"qty"`
	Price         float64   `json:"price"`
	Timestamp     time.Time `json:"timestamp"`
}

type Position struct {
	Symbol      string  `json:"symbol"`
	Qty         float64 `json:"qty"`
	MarketValue float64 `json:"market_value"`
	CostBasis   float64 `json:"cost_basis"`
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

