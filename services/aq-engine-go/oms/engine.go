package oms

import (
	"errors"
	"fmt"
	"math"
	"sync"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/metrics"
	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

type Engine struct {
	mu           sync.RWMutex
	portfolio    models.PortfolioState
	config       models.RiskConfig
	orderHistory map[string]models.OrderIntent
	orderList    []models.OrderIntent
	fills        map[string]models.Fill     // fill_id -> Fill (idempotency ledger)
	fillList     []models.Fill
	positions    map[string]models.Position // confirmed fill position projection
	dailyOrders  int
	lastResetDay string
	isFrozen     bool
	freezeReason string
	frozenAt     *time.Time
	frozenBy     string
	frozenRunID  string
	journalReady bool
	journal      *Journal
}

func NewEngine(initialEquity float64, cfg models.RiskConfig) *Engine {
	return &Engine{
		portfolio: models.PortfolioState{
			Equity:                initialEquity,
			Cash:                  initialEquity,
			GrossExposure:         0,
			DailyPnL:              0,
			PeakEquity:            initialEquity,
			CurrentSymbolExposure: 0,
			CurrentSymbolQty:      0,
			OrdersToday:           0,
			IsFrozen:              false,
		},
		config:       cfg,
		orderHistory: make(map[string]models.OrderIntent),
		orderList:    make([]models.OrderIntent, 0),
		fills:        make(map[string]models.Fill),
		fillList:     make([]models.Fill, 0),
		positions:    make(map[string]models.Position),
		lastResetDay: time.Now().UTC().Format("2006-01-02"),
		isFrozen:     false,
		journalReady: true,
	}
}

func (e *Engine) SetJournal(j *Journal) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.journal = j
	e.journalReady = (j != nil)
}

func (e *Engine) SetJournalReady(ready bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.journalReady = ready
}

func (e *Engine) IsJournalReady() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.journalReady
}

func (e *Engine) Freeze() {
	e.FreezeWithReason("emergency manual freeze", "operator", "")
}

func (e *Engine) FreezeWithReason(reason, by, runID string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.isFrozen = true
	e.portfolio.IsFrozen = true
	e.freezeReason = reason
	e.frozenBy = by
	e.frozenRunID = runID
	now := time.Now().UTC()
	e.frozenAt = &now
	metrics.DefaultRegistry.IncEngineFreeze()
	_ = e.journal.RecordEvent(EventEngineFrozen, nil, nil, reason, by, runID)
}

func (e *Engine) Unfreeze() {
	e.UnfreezeWithReason("manual unfreeze", "operator", "")
}

func (e *Engine) UnfreezeWithReason(reason, by, runID string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.isFrozen = false
	e.portfolio.IsFrozen = false
	e.freezeReason = ""
	e.frozenBy = ""
	e.frozenRunID = ""
	e.frozenAt = nil
	_ = e.journal.RecordEvent(EventEngineUnfrozen, nil, nil, reason, by, runID)
}

func (e *Engine) GetFreezeInfo() (isFrozen bool, reason string, at *time.Time, by string, runID string) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.isFrozen, e.freezeReason, e.frozenAt, e.frozenBy, e.frozenRunID
}

func (e *Engine) IsFrozen() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.isFrozen
}

func (e *Engine) GetPortfolio(symbol string) models.PortfolioState {
	e.mu.RLock()
	defer e.mu.RUnlock()

	p := e.portfolio
	p.OrdersToday = e.dailyOrders
	p.IsFrozen = e.isFrozen
	if symbol != "" {
		if pos, ok := e.positions[symbol]; ok {
			p.CurrentSymbolQty = pos.Qty
			p.CurrentSymbolExposure = pos.MarketValue
		}
	}
	return p
}

func (e *Engine) GetOrderHistory() []models.OrderIntent {
	e.mu.RLock()
	defer e.mu.RUnlock()

	out := make([]models.OrderIntent, len(e.orderList))
	copy(out, e.orderList)
	return out
}

func (e *Engine) GetOrderByClientID(clientOrderID string) (models.OrderIntent, bool) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	ord, exists := e.orderHistory[clientOrderID]
	return ord, exists
}

func (e *Engine) GetPositions() []models.Position {
	e.mu.RLock()
	defer e.mu.RUnlock()

	var list []models.Position
	for _, p := range e.positions {
		if p.Qty != 0 {
			list = append(list, p)
		}
	}
	return list
}

func (e *Engine) GetPosition(symbol string) (models.Position, bool) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	p, exists := e.positions[symbol]
	return p, exists
}

func (e *Engine) GetFills() []models.Fill {
	e.mu.RLock()
	defer e.mu.RUnlock()

	out := make([]models.Fill, len(e.fillList))
	copy(out, e.fillList)
	return out
}

func (e *Engine) GetFillsByClientOrderID(clientOrderID string) []models.Fill {
	e.mu.RLock()
	defer e.mu.RUnlock()

	var out []models.Fill
	for _, f := range e.fillList {
		if f.ClientOrderID == clientOrderID {
			out = append(out, f)
		}
	}
	return out
}

// ApplyFill records a fill idempotently and derives updated position/cash states strictly from confirmed fills.
func (e *Engine) ApplyFill(fill models.Fill) (*models.Position, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	if fill.FillID == "" {
		return nil, errors.New("fill_id cannot be empty")
	}

	// 1. Idempotency check: if fill already processed, return current position
	if _, exists := e.fills[fill.FillID]; exists {
		pos := e.positions[fill.Symbol]
		return &pos, nil
	}

	if fill.Timestamp.IsZero() {
		fill.Timestamp = time.Now().UTC()
	}

	// 2. Record fill in ledger
	e.fills[fill.FillID] = fill
	e.fillList = append(e.fillList, fill)

	// 3. Update OrderIntent in history
	if ord, exists := e.orderHistory[fill.ClientOrderID]; exists {
		prevFilledQty := ord.FilledQtyFloat
		prevCost := prevFilledQty * ord.AverageFillPrice
		newFilledQty := prevFilledQty + fill.Qty
		newCost := prevCost + (fill.Qty * fill.Price)

		ord.FilledQty = int(newFilledQty)
		ord.FilledQtyFloat = newFilledQty
		if newFilledQty > 0 {
			ord.AverageFillPrice = newCost / newFilledQty
		}
		if ord.BrokerOrderID == "" && fill.BrokerOrderID != "" {
			ord.BrokerOrderID = fill.BrokerOrderID
		}

		targetQty := float64(ord.Qty)
		if ord.RequestedQty > 0 {
			targetQty = ord.RequestedQty
		}

		if newFilledQty >= targetQty {
			ord.Status = models.OrderStatusFilled
		} else if newFilledQty > 0 {
			ord.Status = models.OrderStatusPartiallyFilled
		}
		ord.UpdatedAt = fill.Timestamp

		e.orderHistory[fill.ClientOrderID] = ord
		for i := range e.orderList {
			if e.orderList[i].ClientOrderID == fill.ClientOrderID {
				e.orderList[i] = ord
				break
			}
		}
	}

	// 4. Update Position Projection from confirmed fill
	pos := e.positions[fill.Symbol]
	pos.Symbol = fill.Symbol

	if fill.Side == models.SideBuy {
		pos.Qty += fill.Qty
		pos.CostBasis += fill.Qty * fill.Price
		pos.MarketValue = pos.Qty * fill.Price
		e.portfolio.Cash -= fill.Qty * fill.Price
	} else if fill.Side == models.SideSell {
		pos.Qty -= fill.Qty
		pos.MarketValue = pos.Qty * fill.Price
		e.portfolio.Cash += fill.Qty * fill.Price
	}
	e.positions[fill.Symbol] = pos

	// 5. Update portfolio aggregates
	var totalGross float64
	var totalPosVal float64
	for _, p := range e.positions {
		totalGross += math.Abs(p.MarketValue)
		totalPosVal += p.MarketValue
	}
	e.portfolio.GrossExposure = totalGross
	e.portfolio.Equity = e.portfolio.Cash + totalPosVal
	if e.portfolio.Equity > e.portfolio.PeakEquity {
		e.portfolio.PeakEquity = e.portfolio.Equity
	}

	metrics.DefaultRegistry.IncFillsProcessed()
	_ = e.journal.RecordEvent(EventFillRecorded, nil, &fill, fill.ClientOrderID, fill.BrokerOrderID, "")
	return &pos, nil
}

func (e *Engine) UpdateOrderStatus(clientOrderID string, status models.OrderStatus, reasons ...string) {
	e.UpdateOrderStatusAndBrokerID(clientOrderID, status, "", reasons...)
}

func (e *Engine) UpdateOrderStatusAndBrokerID(clientOrderID string, status models.OrderStatus, brokerOrderID string, reasons ...string) {
	e.mu.Lock()
	defer e.mu.Unlock()

	reasonStr := ""
	if len(reasons) > 0 {
		reasonStr = reasons[0]
	}

	if ord, exists := e.orderHistory[clientOrderID]; exists {
		ord.Status = status
		if brokerOrderID != "" {
			ord.BrokerOrderID = brokerOrderID
		}
		if reasonStr != "" {
			ord.Reason = reasonStr
		}
		ord.UpdatedAt = time.Now().UTC()
		e.orderHistory[clientOrderID] = ord
		for i := range e.orderList {
			if e.orderList[i].ClientOrderID == clientOrderID {
				e.orderList[i].Status = status
				if brokerOrderID != "" {
					e.orderList[i].BrokerOrderID = brokerOrderID
				}
				if reasonStr != "" {
					e.orderList[i].Reason = reasonStr
				}
				e.orderList[i].UpdatedAt = ord.UpdatedAt
				break
			}
		}
	}

	switch status {
	case models.OrderStatusAcknowledged:
		_ = e.journal.RecordEvent(EventOrderAcknowledged, nil, nil, clientOrderID, brokerOrderID, reasonStr)
	case models.OrderStatusSubmitFailed:
		_ = e.journal.RecordEvent(EventOrderSubmitFailed, nil, nil, clientOrderID, brokerOrderID, reasonStr)
	case models.OrderStatusCancelled:
		_ = e.journal.RecordEvent(EventOrderCanceled, nil, nil, clientOrderID, brokerOrderID, reasonStr)
	}
}

func (e *Engine) UpdatePortfolio(equity, cash, grossExposure float64) {
	e.mu.Lock()
	defer e.mu.Unlock()

	today := time.Now().UTC().Format("2006-01-02")
	if today != e.lastResetDay {
		e.lastResetDay = today
		e.dailyOrders = 0
	}

	e.portfolio.Equity = equity
	e.portfolio.Cash = cash
	e.portfolio.GrossExposure = grossExposure
	if equity > e.portfolio.PeakEquity {
		e.portfolio.PeakEquity = equity
	}
}

// evaluateRiskRules is an internal helper that evaluates limits without mutating state
func (e *Engine) evaluateRiskRules(p models.PortfolioState, dailyOrders int, order *models.OrderIntent) []string {
	var reasons []string

	// 1. Emergency Kill Switch / Freeze Check
	if e.isFrozen {
		reasons = append(reasons, "Emergency Kill Switch Active: Firm-wide trading is currently FROZEN")
		return reasons
	}

	// 2. Idempotency Check (if already present in history)
	if order.ClientOrderID != "" {
		if _, exists := e.orderHistory[order.ClientOrderID]; exists {
			reasons = append(reasons, fmt.Sprintf("Duplicate client_order_id blocked: %s", order.ClientOrderID))
			return reasons
		}
	}

	// 3. Daily Loss Limit Circuit Breaker
	if p.DailyPnL < 0 && math.Abs(p.DailyPnL) > e.config.MaxDailyLossPct*p.Equity {
		reasons = append(reasons, fmt.Sprintf("Daily loss limit breached: %.2f%% > %.2f%%", math.Abs(p.DailyPnL)/p.Equity*100, e.config.MaxDailyLossPct*100))
	}

	// 4. Drawdown Limit Circuit Breaker
	if p.PeakEquity > 0 {
		dd := (p.PeakEquity - p.Equity) / p.PeakEquity
		if dd > e.config.MaxDrawdownPct {
			reasons = append(reasons, fmt.Sprintf("Drawdown circuit breaker triggered: %.2f%% > %.2f%%", dd*100, e.config.MaxDrawdownPct*100))
		}
	}

	// 5. Daily Orders Count Limit
	if dailyOrders >= e.config.MaxOrdersPerDay {
		reasons = append(reasons, fmt.Sprintf("Maximum daily orders limit reached (%d)", e.config.MaxOrdersPerDay))
	}

	// 6. Minimum Order Notional
	if order.Notional < e.config.MinOrderNotional {
		reasons = append(reasons, fmt.Sprintf("Order notional $%.2f is below minimum threshold $%.2f", order.Notional, e.config.MinOrderNotional))
	}

	// 7. Buy-Specific Balance and Exposure Limits
	if order.Side == models.SideBuy {
		// Minimum Cash Reserve
		minCash := e.config.MinCashReservePct * p.Equity
		if (p.Cash - order.Notional) < minCash {
			reasons = append(reasons, fmt.Sprintf("Cash after order ($%.2f) falls below required reserve ($%.2f)", p.Cash-order.Notional, minCash))
		}

		// Maximum Position Sizing Limit
		newSymExp := p.CurrentSymbolExposure + order.Notional
		maxSymExp := e.config.MaxPositionPct * p.Equity
		if newSymExp > maxSymExp {
			reasons = append(reasons, fmt.Sprintf("Target position ($%.2f) exceeds max allowed position sizing ($%.2f)", newSymExp, maxSymExp))
		}

		// Maximum Gross Portfolio Exposure Limit
		newGross := p.GrossExposure + order.Notional
		maxGross := e.config.MaxGrossExposurePct * p.Equity
		if newGross > maxGross {
			reasons = append(reasons, fmt.Sprintf("Gross exposure ($%.2f) exceeds max allowed portfolio limit ($%.2f)", newGross, maxGross))
		}
	}

	return reasons
}

// CheckRisk performs pure deterministic pre-trade risk evaluation without any side effects or mutations.
// It does not insert an order, increment dailyOrders, reserve exposure, modify portfolio, or alter idempotency state.
func (e *Engine) CheckRisk(order *models.OrderIntent) models.RiskDecision {
	e.mu.RLock()
	defer e.mu.RUnlock()

	reasons := e.evaluateRiskRules(e.portfolio, e.dailyOrders, order)
	traceID := order.TraceID

	ordCopy := *order
	if len(reasons) > 0 {
		ordCopy.Status = models.OrderStatusRejected
		return models.RiskDecision{
			Approved: false,
			Order:    &ordCopy,
			Reasons:  reasons,
			TraceID:  traceID,
		}
	}

	ordCopy.Status = models.OrderStatusApproved
	return models.RiskDecision{
		Approved: true,
		Order:    &ordCopy,
		Reasons:  nil,
		TraceID:  traceID,
	}
}

// EvaluateRisk is an alias for CheckRisk to preserve backward compatibility.
func (e *Engine) EvaluateRisk(order *models.OrderIntent) models.RiskDecision {
	return e.CheckRisk(order)
}

// ReserveOrder atomically validates risk and idempotency, registers the order in history as SUBMITTING,
// and increments the daily orders counter.
func (e *Engine) ReserveOrder(order *models.OrderIntent) (*models.OrderIntent, models.RiskDecision) {
	e.mu.Lock()
	defer e.mu.Unlock()

	today := time.Now().UTC().Format("2006-01-02")
	if today != e.lastResetDay {
		e.lastResetDay = today
		e.dailyOrders = 0
	}

	reasons := e.evaluateRiskRules(e.portfolio, e.dailyOrders, order)
	traceID := order.TraceID

	ordCopy := *order
	if len(reasons) > 0 {
		ordCopy.Status = models.OrderStatusRejected
		metrics.DefaultRegistry.IncOrdersRejected()
		return nil, models.RiskDecision{
			Approved: false,
			Order:    &ordCopy,
			Reasons:  reasons,
			TraceID:  traceID,
		}
	}

	if ordCopy.CreatedAt.IsZero() {
		ordCopy.CreatedAt = time.Now().UTC()
	}
	ordCopy.Status = models.OrderStatusSubmitting
	ordCopy.UpdatedAt = ordCopy.CreatedAt

	e.orderHistory[ordCopy.ClientOrderID] = ordCopy
	e.orderList = append(e.orderList, ordCopy)
	e.dailyOrders++

	_ = e.journal.RecordEvent(EventOrderSubmitting, &ordCopy, nil, ordCopy.ClientOrderID, "", "")

	return &ordCopy, models.RiskDecision{
		Approved: true,
		Order:    &ordCopy,
		Reasons:  nil,
		TraceID:  traceID,
	}
}

func (e *Engine) replayEvent(evt JournalEvent) {
	e.mu.Lock()
	defer e.mu.Unlock()

	switch evt.Type {
	case EventOrderReserved, EventOrderSubmitting:
		if evt.Order != nil {
			ord := *evt.Order
			if ord.UpdatedAt.IsZero() {
				ord.UpdatedAt = ord.CreatedAt
			}
			e.orderHistory[ord.ClientOrderID] = ord
			e.orderList = append(e.orderList, ord)
			e.dailyOrders++
		}
	case EventOrderAcknowledged:
		if ord, ok := e.orderHistory[evt.ClientOrderID]; ok {
			ord.Status = models.OrderStatusAcknowledged
			if evt.BrokerOrderID != "" {
				ord.BrokerOrderID = evt.BrokerOrderID
			}
			ord.UpdatedAt = evt.Timestamp
			e.orderHistory[evt.ClientOrderID] = ord
			for i := range e.orderList {
				if e.orderList[i].ClientOrderID == evt.ClientOrderID {
					e.orderList[i] = ord
					break
				}
			}
		}
	case EventOrderSubmitFailed:
		if ord, ok := e.orderHistory[evt.ClientOrderID]; ok {
			ord.Status = models.OrderStatusSubmitFailed
			ord.Reason = evt.Reason
			ord.UpdatedAt = evt.Timestamp
			e.orderHistory[evt.ClientOrderID] = ord
			for i := range e.orderList {
				if e.orderList[i].ClientOrderID == evt.ClientOrderID {
					e.orderList[i] = ord
					break
				}
			}
		}
	case EventOrderCanceled:
		if ord, ok := e.orderHistory[evt.ClientOrderID]; ok {
			ord.Status = models.OrderStatusCancelled
			ord.UpdatedAt = evt.Timestamp
			e.orderHistory[evt.ClientOrderID] = ord
			for i := range e.orderList {
				if e.orderList[i].ClientOrderID == evt.ClientOrderID {
					e.orderList[i] = ord
					break
				}
			}
		}
	case EventFillRecorded:
		if evt.Fill != nil {
			fill := *evt.Fill
			if _, exists := e.fills[fill.FillID]; !exists {
				e.fills[fill.FillID] = fill
				e.fillList = append(e.fillList, fill)

				if ord, exists := e.orderHistory[fill.ClientOrderID]; exists {
					prevFilledQty := ord.FilledQtyFloat
					prevCost := prevFilledQty * ord.AverageFillPrice
					newFilledQty := prevFilledQty + fill.Qty
					newCost := prevCost + (fill.Qty * fill.Price)

					ord.FilledQty = int(newFilledQty)
					ord.FilledQtyFloat = newFilledQty
					if newFilledQty > 0 {
						ord.AverageFillPrice = newCost / newFilledQty
					}
					if ord.BrokerOrderID == "" && fill.BrokerOrderID != "" {
						ord.BrokerOrderID = fill.BrokerOrderID
					}

					targetQty := float64(ord.Qty)
					if ord.RequestedQty > 0 {
						targetQty = ord.RequestedQty
					}

					if newFilledQty >= targetQty {
						ord.Status = models.OrderStatusFilled
					} else if newFilledQty > 0 {
						ord.Status = models.OrderStatusPartiallyFilled
					}
					ord.UpdatedAt = fill.Timestamp

					e.orderHistory[fill.ClientOrderID] = ord
					for i := range e.orderList {
						if e.orderList[i].ClientOrderID == fill.ClientOrderID {
							e.orderList[i] = ord
							break
						}
					}
				}

				pos := e.positions[fill.Symbol]
				pos.Symbol = fill.Symbol

				if fill.Side == models.SideBuy {
					pos.Qty += fill.Qty
					pos.CostBasis += fill.Qty * fill.Price
					pos.MarketValue = pos.Qty * fill.Price
					e.portfolio.Cash -= fill.Qty * fill.Price
				} else if fill.Side == models.SideSell {
					pos.Qty -= fill.Qty
					pos.MarketValue = pos.Qty * fill.Price
					e.portfolio.Cash += fill.Qty * fill.Price
				}
				e.positions[fill.Symbol] = pos

				var totalGross float64
				var totalPosVal float64
				for _, p := range e.positions {
					totalGross += math.Abs(p.MarketValue)
					totalPosVal += p.MarketValue
				}
				e.portfolio.GrossExposure = totalGross
				e.portfolio.Equity = e.portfolio.Cash + totalPosVal
				if e.portfolio.Equity > e.portfolio.PeakEquity {
					e.portfolio.PeakEquity = e.portfolio.Equity
				}
			}
		}
	case EventEngineFrozen:
		e.isFrozen = true
		e.portfolio.IsFrozen = true
	case EventEngineUnfrozen:
		e.isFrozen = false
		e.portfolio.IsFrozen = false
	}
}

// Submit performs the full order submission state machine:
// CheckRisk/ReserveOrder -> SUBMITTING -> broker SubmitOrder -> ACKNOWLEDGED or SUBMIT_FAILED.
func (e *Engine) Submit(order *models.OrderIntent, b broker.BrokerAdapter) (*broker.BrokerOrder, models.RiskDecision, error) {
	if b == nil {
		return nil, models.RiskDecision{Approved: false, Reasons: []string{"broker adapter is nil"}}, errors.New("broker adapter is nil")
	}

	reserved, decision := e.ReserveOrder(order)
	if !decision.Approved {
		return nil, decision, fmt.Errorf("risk rejection: %v", decision.Reasons)
	}

	resp, err := b.SubmitOrder(reserved)
	if err != nil {
		e.UpdateOrderStatus(order.ClientOrderID, models.OrderStatusSubmitFailed, err.Error())
		return nil, decision, err
	}

	brokerOrderID := ""
	if resp != nil {
		brokerOrderID = resp.ID
	}
	e.UpdateOrderStatusAndBrokerID(order.ClientOrderID, models.OrderStatusAcknowledged, brokerOrderID)
	metrics.DefaultRegistry.IncOrdersSubmitted()
	return resp, decision, nil
}

// ConstructLocalSnapshot builds an authentic, non-fabricated snapshot of local OMS orders, confirmed positions, and cash state for reconciliation.
func (e *Engine) ConstructLocalSnapshot() reconciliation.LocalState {
	e.mu.RLock()
	defer e.mu.RUnlock()

	now := time.Now().UTC()
	localOrders := make(map[string]reconciliation.OrderState)
	for _, ord := range e.orderList {
		localOrders[ord.ClientOrderID] = reconciliation.OrderState{
			ClientOrderID: ord.ClientOrderID,
			BrokerOrderID: ord.BrokerOrderID,
			Symbol:        ord.Symbol,
			Side:          string(ord.Side),
			RequestedQty:  ord.Qty,
			FilledQty:     ord.FilledQty,
			Status:        string(ord.Status),
			CreatedAt:     ord.CreatedAt,
			UpdatedAt:     ord.UpdatedAt,
		}
	}

	localPositions := make(map[string]reconciliation.PositionState)
	for sym, pos := range e.positions {
		if pos.Qty != 0 {
			localPositions[sym] = reconciliation.PositionState{
				Symbol:      pos.Symbol,
				Qty:         pos.Qty,
				MarketValue: pos.MarketValue,
				CostBasis:   pos.CostBasis,
			}
		}
	}

	return reconciliation.LocalState{
		Orders:    localOrders,
		Positions: localPositions,
		Cash:      e.portfolio.Cash,
		Equity:    e.portfolio.Equity,
		Timestamp: now,
	}
}

