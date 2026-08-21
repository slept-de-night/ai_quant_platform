package reconciliation

import (
	"math"
	"strings"
	"sync"
	"time"
)

type DiscrepancyType string

const (
	DiscrepancyUnknownBrokerOrder DiscrepancyType = "UNKNOWN_BROKER_ORDER"
	DiscrepancyMissingBrokerOrder DiscrepancyType = "MISSING_BROKER_ORDER"
	DiscrepancyFillQtyMismatch    DiscrepancyType = "FILL_QTY_MISMATCH"
	DiscrepancyPositionMismatch   DiscrepancyType = "POSITION_MISMATCH"
	DiscrepancyCashMismatch       DiscrepancyType = "CASH_MISMATCH"
	DiscrepancyStaleLocalOrder    DiscrepancyType = "STALE_LOCAL_ORDER"
)

type Severity string

const (
	SeverityCritical Severity = "CRITICAL"
	SeverityHigh     Severity = "HIGH"
	SeverityMedium   Severity = "MEDIUM"
	SeverityLow      Severity = "LOW"
)

type OrderState struct {
	ClientOrderID string    `json:"client_order_id"`
	BrokerOrderID string    `json:"broker_order_id,omitempty"`
	Symbol        string    `json:"symbol"`
	Side          string    `json:"side"`
	RequestedQty  int       `json:"requested_qty"`
	FilledQty     int       `json:"filled_qty"`
	Status        string    `json:"status"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

type PositionState struct {
	Symbol      string  `json:"symbol"`
	Qty         float64 `json:"qty"`
	MarketValue float64 `json:"market_value"`
	CostBasis   float64 `json:"cost_basis"`
}

type LocalState struct {
	Orders    map[string]OrderState    `json:"orders"`
	Positions map[string]PositionState `json:"positions"`
	Cash      float64                  `json:"cash"`
	Equity    float64                  `json:"equity"`
	Timestamp time.Time                `json:"timestamp"`
}

type BrokerState struct {
	Orders    map[string]OrderState    `json:"orders"`
	Positions map[string]PositionState `json:"positions"`
	Cash      float64                  `json:"cash"`
	Equity    float64                  `json:"equity"`
	Timestamp time.Time                `json:"timestamp"`
}

type Discrepancy struct {
	Type          DiscrepancyType `json:"type"`
	Severity      Severity        `json:"severity"`
	Symbol        string          `json:"symbol,omitempty"`
	ClientOrderID string          `json:"client_order_id,omitempty"`
	BrokerOrderID string          `json:"broker_order_id,omitempty"`
	LocalValue    interface{}     `json:"local_value,omitempty"`
	BrokerValue   interface{}     `json:"broker_value,omitempty"`
	Message       string          `json:"message"`
	DetectedAt    time.Time       `json:"detected_at"`
}

type Diff struct {
	Discrepancies []Discrepancy `json:"discrepancies"`
	TotalCount    int           `json:"total_count"`
	HasErrors     bool          `json:"has_errors"`
	HasCritical   bool          `json:"has_critical"`
	GeneratedAt   time.Time     `json:"generated_at"`
}

type Reconciler struct {
	mu            sync.RWMutex
	QtyTolerance  float64
	CashTolerance float64
	StaleAfter    time.Duration
	MaxAge        time.Duration
	LastRunAt     *time.Time
	LastDiff      *Diff
	LastBroker    string
}

func NewReconciler(qtyTolerance, cashTolerance float64, staleAfter time.Duration) *Reconciler {
	return &Reconciler{
		QtyTolerance:  qtyTolerance,
		CashTolerance: cashTolerance,
		StaleAfter:    staleAfter,
		MaxAge:        5 * time.Minute,
	}
}

func (r *Reconciler) SetMaxAge(d time.Duration) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if d > 0 {
		r.MaxAge = d
	}
}

func (r *Reconciler) RecordRun(brokerName string, diff Diff) {
	r.mu.Lock()
	defer r.mu.Unlock()
	t := diff.GeneratedAt
	r.LastRunAt = &t
	r.LastDiff = &diff
	r.LastBroker = brokerName
}

func (r *Reconciler) GetSummary(now time.Time) (status string, isFresh bool, lastRun *time.Time, critCount int, totCount int, broker string) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if r.LastDiff == nil || r.LastRunAt == nil {
		return "UNKNOWN", false, nil, 0, 0, ""
	}

	lastRun = r.LastRunAt
	broker = r.LastBroker
	critCount = 0
	totCount = r.LastDiff.TotalCount
	for _, d := range r.LastDiff.Discrepancies {
		if d.Severity == SeverityCritical {
			critCount++
		}
	}

	age := now.Sub(*r.LastRunAt)
	if r.MaxAge > 0 && age > r.MaxAge {
		return "STALE", false, lastRun, critCount, totCount, broker
	}

	if r.LastDiff.HasCritical {
		return "MISMATCH", true, lastRun, critCount, totCount, broker
	}

	if r.LastDiff.TotalCount == 0 {
		return "CLEAN", true, lastRun, critCount, totCount, broker
	}

	return "WARNING", true, lastRun, critCount, totCount, broker
}

func (r *Reconciler) Reconcile(local LocalState, broker BrokerState) Diff {
	now := time.Now().UTC()
	var discrepancies []Discrepancy

	// 1. Check Orders: Local vs Broker
	for clientID, localOrd := range local.Orders {
		brokerOrd, existsInBroker := broker.Orders[clientID]
		if !existsInBroker {
			// If local order is submitted/open and not in broker, mark missing
			if isWorkingStatus(localOrd.Status) {
				discrepancies = append(discrepancies, Discrepancy{
					Type:          DiscrepancyMissingBrokerOrder,
					Severity:      SeverityHigh,
					Symbol:        localOrd.Symbol,
					ClientOrderID: clientID,
					LocalValue:    localOrd.Status,
					BrokerValue:   nil,
					Message:       "Local order is OPEN/SUBMITTED but missing from broker state",
					DetectedAt:    now,
				})
			}
			continue
		}

		// Check fill quantity mismatch
		if localOrd.FilledQty != brokerOrd.FilledQty {
			discrepancies = append(discrepancies, Discrepancy{
				Type:          DiscrepancyFillQtyMismatch,
				Severity:      SeverityHigh,
				Symbol:        localOrd.Symbol,
				ClientOrderID: clientID,
				BrokerOrderID: brokerOrd.BrokerOrderID,
				LocalValue:    localOrd.FilledQty,
				BrokerValue:   brokerOrd.FilledQty,
				Message:       "Filled quantity mismatch between OMS and broker",
				DetectedAt:    now,
			})
		}

		// Check stale status
		if r.isStale(localOrd, brokerOrd, now) {
			discrepancies = append(discrepancies, Discrepancy{
				Type:          DiscrepancyStaleLocalOrder,
				Severity:      SeverityMedium,
				Symbol:        localOrd.Symbol,
				ClientOrderID: clientID,
				BrokerOrderID: brokerOrd.BrokerOrderID,
				LocalValue:    localOrd.Status,
				BrokerValue:   brokerOrd.Status,
				Message:       "Local OMS order status is stale compared to broker truth",
				DetectedAt:    now,
			})
		}
	}

	// 2. Check for Unknown Broker Orders
	for clientID, brokerOrd := range broker.Orders {
		if _, existsInLocal := local.Orders[clientID]; !existsInLocal {
			discrepancies = append(discrepancies, Discrepancy{
				Type:          DiscrepancyUnknownBrokerOrder,
				Severity:      SeverityCritical,
				Symbol:        brokerOrd.Symbol,
				ClientOrderID: clientID,
				BrokerOrderID: brokerOrd.BrokerOrderID,
				LocalValue:    nil,
				BrokerValue:   brokerOrd.Status,
				Message:       "Order exists on broker but is unknown to local OMS",
				DetectedAt:    now,
			})
		}
	}

	// 3. Check Positions Mismatch
	allSymbols := make(map[string]bool)
	for s := range local.Positions {
		allSymbols[s] = true
	}
	for s := range broker.Positions {
		allSymbols[s] = true
	}

	for sym := range allSymbols {
		localPos := local.Positions[sym]
		brokerPos := broker.Positions[sym]

		if !within(localPos.Qty, brokerPos.Qty, r.QtyTolerance) {
			discrepancies = append(discrepancies, Discrepancy{
				Type:        DiscrepancyPositionMismatch,
				Severity:    SeverityCritical,
				Symbol:      sym,
				LocalValue:  localPos.Qty,
				BrokerValue: brokerPos.Qty,
				Message:     "Position quantity mismatch between OMS portfolio and broker",
				DetectedAt:  now,
			})
		}
	}

	// 4. Check Cash Mismatch
	if !within(local.Cash, broker.Cash, r.CashTolerance) {
		discrepancies = append(discrepancies, Discrepancy{
			Type:        DiscrepancyCashMismatch,
			Severity:    SeverityHigh,
			LocalValue:  local.Cash,
			BrokerValue: broker.Cash,
			Message:     "Cash balance mismatch between OMS and broker ledger",
			DetectedAt:  now,
		})
	}

	hasCritical := false
	for _, d := range discrepancies {
		if d.Severity == SeverityCritical {
			hasCritical = true
			break
		}
	}

	return Diff{
		Discrepancies: discrepancies,
		TotalCount:    len(discrepancies),
		HasErrors:     len(discrepancies) > 0,
		HasCritical:   hasCritical,
		GeneratedAt:   now,
	}
}

func (r *Reconciler) isStale(local, broker OrderState, detectedAt time.Time) bool {
	if r.StaleAfter <= 0 || local.UpdatedAt.IsZero() {
		return false
	}
	if canonicalStatus(local.Status) == canonicalStatus(broker.Status) {
		return false
	}
	return !local.UpdatedAt.Add(r.StaleAfter).After(detectedAt)
}

func within(a, b, tolerance float64) bool {
	if tolerance < 0 {
		tolerance = -tolerance
	}
	return math.Abs(a-b) <= tolerance
}

func canonicalStatus(status string) string {
	switch strings.ToUpper(strings.TrimSpace(status)) {
	case "PENDING", "APPROVED", "SUBMITTED", "ACCEPTED", "NEW", "PENDING_NEW", "ACCEPTED_FOR_BIDDING", "SUBMITTING", "ACKNOWLEDGED":
		return "OPEN"
	case "PARTIALLY_FILLED", "PARTIAL_FILL", "PARTIAL":
		return "PARTIALLY_FILLED"
	case "FILLED", "FILL":
		return "FILLED"
	case "CANCELLED", "CANCELED", "DONE_FOR_DAY", "EXPIRED", "REPLACED":
		return "CANCELLED"
	case "REJECTED", "SUSPENDED", "STOPPED", "SUBMIT_FAILED":
		return "REJECTED"
	default:
		return strings.ToUpper(strings.TrimSpace(status))
	}
}

func isWorkingStatus(status string) bool {
	switch canonicalStatus(status) {
	case "OPEN", "PARTIALLY_FILLED":
		return true
	default:
		return false
	}
}
