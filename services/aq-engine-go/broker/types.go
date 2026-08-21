package broker

import (
	"strings"
	"time"
)

type BrokerKind string

const (
	BrokerKindPaper  BrokerKind = "paper"
	BrokerKindWebull BrokerKind = "webull"
	BrokerKindAlpaca BrokerKind = "alpaca"
	BrokerKindIBKR   BrokerKind = "ibkr"
)

type Environment string

const (
	EnvSimulation Environment = "simulation"
	EnvPaper      Environment = "paper"
	EnvLive       Environment = "live"
)

type BrokerOrderStatus string

const (
	BrokerOrderStatusSubmitting             BrokerOrderStatus = "SUBMITTING"
	BrokerOrderStatusAcknowledged           BrokerOrderStatus = "ACKNOWLEDGED"
	BrokerOrderStatusPartiallyFilled        BrokerOrderStatus = "PARTIALLY_FILLED"
	BrokerOrderStatusFilled                 BrokerOrderStatus = "FILLED"
	BrokerOrderStatusCancelPending          BrokerOrderStatus = "CANCEL_PENDING"
	BrokerOrderStatusCanceled               BrokerOrderStatus = "CANCELED"
	BrokerOrderStatusExpired                BrokerOrderStatus = "EXPIRED"
	BrokerOrderStatusRejected                BrokerOrderStatus = "REJECTED"
	BrokerOrderStatusSubmitFailed           BrokerOrderStatus = "SUBMIT_FAILED"
	BrokerOrderStatusReconciliationRequired BrokerOrderStatus = "RECONCILIATION_REQUIRED"
)

// NormalizeBrokerStatus maps diverse broker-specific raw status strings into a single deterministic internal status enum.
func NormalizeBrokerStatus(raw string) BrokerOrderStatus {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "new", "accepted", "acknowledged", "held", "pending", "approved":
		return BrokerOrderStatusAcknowledged
	case "submitting", "pending_new", "created", "open":
		return BrokerOrderStatusSubmitting
	case "partially_filled", "partiallyfilled", "partial_fill", "partial":
		return BrokerOrderStatusPartiallyFilled
	case "filled", "executed", "complete", "completed":
		return BrokerOrderStatusFilled
	case "pending_cancel", "cancel_pending", "cancelling":
		return BrokerOrderStatusCancelPending
	case "canceled", "cancelled", "done_for_day", "stopped", "suspended":
		return BrokerOrderStatusCanceled
	case "expired":
		return BrokerOrderStatusExpired
	case "rejected", "declined":
		return BrokerOrderStatusRejected
	case "failed", "submit_failed", "error":
		return BrokerOrderStatusSubmitFailed
	default:
		return BrokerOrderStatusAcknowledged
	}
}

type BrokerOrder struct {
	ID               string            `json:"id"`
	BrokerOrderID    string            `json:"broker_order_id"`
	ClientOrderID    string            `json:"client_order_id"`
	Symbol           string            `json:"symbol"`
	Side             string            `json:"side"`
	Qty              int               `json:"qty"`
	RequestedQty     float64           `json:"requested_qty"`
	FilledQty        int               `json:"filled_qty"`
	FilledQtyFloat   float64           `json:"filled_qty_float,omitempty"`
	AverageFillPrice float64           `json:"average_fill_price,omitempty"`
	AvgPrice         float64           `json:"avg_price,omitempty"`
	LimitPrice       float64           `json:"limit_price,omitempty"`
	Status           BrokerOrderStatus `json:"status"`
	RawStatus        string            `json:"raw_status,omitempty"`
	CreatedAt        time.Time         `json:"created_at"`
	UpdatedAt        time.Time         `json:"updated_at"`
}

type BrokerPosition struct {
	Symbol      string  `json:"symbol"`
	Qty         float64 `json:"qty"`
	MarketValue float64 `json:"market_value"`
	CostBasis   float64 `json:"cost_basis"`
}

type AccountState struct {
	Cash        float64 `json:"cash"`
	Equity      float64 `json:"equity"`
	BuyingPower float64 `json:"buying_power"`
	Currency    string  `json:"currency"`
}

// BrokerAccount is an alias for AccountState for normalized contract compatibility.
type BrokerAccount = AccountState

type Health struct {
	Ready         bool        `json:"ready"`
	Connected     bool        `json:"connected"`
	Broker        BrokerKind  `json:"broker"`
	Name          string      `json:"name"`
	Environment   Environment `json:"environment"`
	Message       string      `json:"message"`
	LastCheckedAt time.Time   `json:"last_checked_at"`
}
