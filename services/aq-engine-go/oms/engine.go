package oms

import (
	"errors"
	"fmt"
	"math"
	"sync"
	"time"

	"strings"

	"aq-engine-go/broker"
	"aq-engine-go/market"
	"aq-engine-go/metrics"
	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

type Engine struct {
	mu                 sync.RWMutex
	portfolio          models.PortfolioState
	config             models.RiskConfig
	orderHistory       map[string]models.OrderIntent
	orderList          []models.OrderIntent
	fills              map[string]models.Fill     // fill_id -> Fill (idempotency ledger)
	fillList           []models.Fill
	positions          map[string]models.Position // confirmed fill position projection
	dailyOrders        int
	lastResetDay       string
	isFrozen           bool
	freezeReason       string
	frozenAt           *time.Time
	frozenBy           string
	frozenRunID        string
	journalReady       bool
	journal            *Journal
	gateway            *market.Gateway
	requireGatewayTick bool
	allowShorting      bool
	slippageBuffer     float64
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
		config:             cfg,
		orderHistory:       make(map[string]models.OrderIntent),
		orderList:          make([]models.OrderIntent, 0),
		fills:              make(map[string]models.Fill),
		fillList:           make([]models.Fill, 0),
		positions:          make(map[string]models.Position),
		lastResetDay:       time.Now().UTC().Format("2006-01-02"),
		isFrozen:           false,
		journalReady:       true,
		requireGatewayTick: false,
		allowShorting:      false,
		slippageBuffer:     0.005,
	}
}

func (e *Engine) SetGateway(g *market.Gateway) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.gateway = g
}

func (e *Engine) SetRequireGatewayTick(req bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.requireGatewayTick = req
}

func (e *Engine) SetAllowShorting(allow bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.allowShorting = allow
}

func (e *Engine) SetSlippageBuffer(buf float64) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.slippageBuffer = buf
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

// recordEventLocked durably writes a critical journal event and fails closed if disk write/fsync fails.
func (e *Engine) recordEventLocked(evtType JournalEventType, order *models.OrderIntent, fill *models.Fill, clientOrderID, brokerOrderID, reason string) error {
	if e.journal == nil {
		if !e.journalReady {
			return errors.New("durable journal is not ready")
		}
		return nil
	}

	err := e.journal.RecordEvent(evtType, order, fill, clientOrderID, brokerOrderID, reason)
	if err != nil {
		e.journalReady = false
		e.isFrozen = true
		e.portfolio.IsFrozen = true
		e.freezeReason = fmt.Sprintf("durable journal write failure on %s: %v", evtType, err)
		now := time.Now().UTC()
		e.frozenAt = &now
		e.frozenBy = "journal_system"
		metrics.DefaultRegistry.IncEngineFreeze()
		return fmt.Errorf("journal write error (%s): %w", evtType, err)
	}
	return nil
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
	_ = e.recordEventLocked(EventEngineFrozen, nil, nil, reason, by, runID)
}

func (e *Engine) Unfreeze() {
	_ = e.UnfreezeWithReason("manual unfreeze", "operator", "")
}

func (e *Engine) UnfreezeWithReason(reason, by, runID string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	if !e.journalReady {
		return errors.New("cannot unfreeze: durable journal is not ready")
	}

	err := e.recordEventLocked(EventEngineUnfrozen, nil, nil, reason, by, runID)
	if err != nil {
		return fmt.Errorf("failed to journal unfreeze event: %w", err)
	}

	e.isFrozen = false
	e.portfolio.IsFrozen = false
	e.freezeReason = ""
	e.frozenBy = ""
	e.frozenRunID = ""
	e.frozenAt = nil
	return nil
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

// computeActiveReservationsLocked computes aggregated exposure and cash reservations from all outstanding/in-flight orders.
func (e *Engine) computeActiveReservationsLocked(targetSymbol string) (reservedCash, reservedBuyNotional, reservedGross, reservedSymbolExposure, reservedSellQty float64) {
	slippage := e.slippageBuffer
	if slippage <= 0 {
		slippage = 0.005
	}

	for _, ord := range e.orderHistory {
		switch ord.Status {
		case models.OrderStatusSubmitting,
			models.OrderStatusSubmissionUnknown,
			models.OrderStatusAcknowledged,
			models.OrderStatusPartiallyFilled,
			models.OrderStatusCancelPending:

			targetQty := float64(ord.Qty)
			if ord.RequestedQty > 0 {
				targetQty = ord.RequestedQty
			}
			remainingQty := targetQty - ord.FilledQtyFloat
			if remainingQty <= 0 {
				continue
			}

			price := ord.ReferencePrice
			if price <= 0 && e.gateway != nil {
				if tick, ok := e.gateway.GetLatestTick(ord.Symbol); ok && tick.Price > 0 {
					price = tick.Price
				}
			}

			if ord.Side == models.SideBuy {
				notionalWithSlippage := remainingQty * price * (1.0 + slippage)
				reservedCash += notionalWithSlippage
				reservedBuyNotional += notionalWithSlippage
				reservedGross += notionalWithSlippage
				if strings.EqualFold(ord.Symbol, targetSymbol) {
					reservedSymbolExposure += notionalWithSlippage
				}
			} else if ord.Side == models.SideSell {
				notional := remainingQty * price
				reservedGross += notional
				if strings.EqualFold(ord.Symbol, targetSymbol) {
					reservedSellQty += remainingQty
				}
			}
		}
	}
	return
}

func (e *Engine) GetPortfolio(symbol string) models.PortfolioState {
	e.mu.RLock()
	defer e.mu.RUnlock()

	p := e.portfolio
	p.OrdersToday = e.dailyOrders
	p.IsFrozen = e.isFrozen

	resCash, resBuyNotional, resGross, resSymExp, resSellQty := e.computeActiveReservationsLocked(symbol)
	p.ReservedCash = resCash
	p.ReservedBuyNotional = resBuyNotional
	p.ReservedGrossExposure = resGross
	p.ReservedSymbolExposure = resSymExp
	p.ReservedSellQty = resSellQty

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

	// 2. Durably record fill event to journal BEFORE mutating in-memory state (write-ahead)
	if err := e.recordEventLocked(EventFillRecorded, nil, &fill, fill.ClientOrderID, fill.BrokerOrderID, ""); err != nil {
		return nil, fmt.Errorf("durable journal write failed for fill %s: %w", fill.FillID, err)
	}

	// 3. Record fill in ledger
	e.fills[fill.FillID] = fill
	e.fillList = append(e.fillList, fill)

	// 4. Update OrderIntent in history
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

	// 5. Update Position Projection from confirmed fill
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

	// 6. Update portfolio aggregates
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
	return &pos, nil
}

func (e *Engine) UpdateOrderStatus(clientOrderID string, status models.OrderStatus, reasons ...string) error {
	return e.UpdateOrderStatusAndBrokerID(clientOrderID, status, "", reasons...)
}

func (e *Engine) UpdateOrderStatusAndBrokerID(clientOrderID string, status models.OrderStatus, brokerOrderID string, reasons ...string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	reasonStr := ""
	if len(reasons) > 0 {
		reasonStr = reasons[0]
	}

	var evtType JournalEventType
	switch status {
	case models.OrderStatusAcknowledged:
		evtType = EventOrderAcknowledged
	case models.OrderStatusSubmitFailed:
		evtType = EventOrderSubmitFailed
	case models.OrderStatusCancelled:
		evtType = EventOrderCanceled
	case models.OrderStatusCancelPending:
		evtType = EventCancelRequested
	case models.OrderStatusSubmissionUnknown:
		evtType = EventSubmissionUnknown
	}

	if evtType != "" {
		if err := e.recordEventLocked(evtType, nil, nil, clientOrderID, brokerOrderID, reasonStr); err != nil {
			return fmt.Errorf("failed to journal order status %s: %w", status, err)
		}
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
	return nil
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

	// 1. Emergency Kill Switch / Freeze & Journal Readiness Check
	if e.isFrozen {
		reasons = append(reasons, "Emergency Kill Switch Active: Firm-wide trading is currently FROZEN")
		return reasons
	}
	if !e.journalReady {
		reasons = append(reasons, "Execution blocked: durable journal is not ready/healthy")
		return reasons
	}

	// 2. Order Input Structural Validation
	order.Symbol = strings.ToUpper(strings.TrimSpace(order.Symbol))
	if order.Symbol == "" {
		reasons = append(reasons, "Order symbol cannot be empty")
		return reasons
	}

	if order.ClientOrderID == "" {
		reasons = append(reasons, "client_order_id cannot be empty")
		return reasons
	}

	// Idempotency Check (if already present in history)
	if _, exists := e.orderHistory[order.ClientOrderID]; exists {
		reasons = append(reasons, fmt.Sprintf("Duplicate client_order_id blocked: %s", order.ClientOrderID))
		return reasons
	}

	// Executable Side Check (HOLD is strictly prohibited for broker order execution)
	sideStr := strings.ToLower(strings.TrimSpace(string(order.Side)))
	if sideStr != "buy" && sideStr != "sell" {
		reasons = append(reasons, fmt.Sprintf("Invalid or non-executable order side '%s'; HOLD and non-trading sides are prohibited", order.Side))
		return reasons
	}

	// Quantity Validation (positive whole shares required)
	if order.Qty <= 0 {
		reasons = append(reasons, fmt.Sprintf("Order quantity must be positive, got %d", order.Qty))
	}
	if order.RequestedQty > 0 && order.RequestedQty != float64(int(order.RequestedQty)) {
		reasons = append(reasons, fmt.Sprintf("Fractional order quantity (%.4f) not supported; whole shares required", order.RequestedQty))
	}

	// 3. Authoritative Pre-Trade Pricing & Freshness Validation
	var refPrice float64
	hasValidGatewayTick := false

	if e.gateway != nil {
		tick, exists := e.gateway.GetLatestTick(order.Symbol)
		if exists && tick.Price > 0 && !math.IsNaN(tick.Price) && !math.IsInf(tick.Price, 0) {
			now := time.Now().UTC()
			staleness := now.Sub(tick.Timestamp).Seconds()
			if e.config.MaxTickStalenessSeconds > 0 && staleness > e.config.MaxTickStalenessSeconds {
				reasons = append(reasons, fmt.Sprintf("Market data for %s is stale (age %.1fs > max %.1fs)", order.Symbol, staleness, e.config.MaxTickStalenessSeconds))
			} else {
				refPrice = tick.Price
				hasValidGatewayTick = true

				// Check client reference price divergence if supplied
				if order.ReferencePrice > 0 {
					dev := math.Abs(order.ReferencePrice - tick.Price) / tick.Price
					if dev > 0.05 {
						reasons = append(reasons, fmt.Sprintf("Client reference price $%.2f deviates %.1f%% from authoritative market price $%.2f", order.ReferencePrice, dev*100, tick.Price))
					}
				}
			}
		} else if e.requireGatewayTick {
			reasons = append(reasons, fmt.Sprintf("Authoritative market price unavailable for %s", order.Symbol))
		}
	}

	if !hasValidGatewayTick {
		if order.ReferencePrice > 0 && !math.IsNaN(order.ReferencePrice) && !math.IsInf(order.ReferencePrice, 0) {
			refPrice = order.ReferencePrice
		} else if refPrice <= 0 {
			reasons = append(reasons, fmt.Sprintf("Authoritative market price unavailable for %s", order.Symbol))
		}
	}

	// 4. Conservative Risk Notional Calculation
	slippage := e.slippageBuffer
	if slippage <= 0 {
		slippage = 0.005
	}
	conservativePrice := refPrice
	if order.Side == models.SideBuy {
		conservativePrice = refPrice * (1.0 + slippage)
	} else if order.Side == models.SideSell {
		conservativePrice = refPrice * (1.0 - slippage)
	}

	riskNotional := float64(order.Qty) * conservativePrice
	if order.Notional <= 0 || order.Notional < float64(order.Qty)*refPrice*0.90 {
		order.Notional = float64(order.Qty) * refPrice
	}
	if order.ReferencePrice <= 0 && refPrice > 0 {
		order.ReferencePrice = refPrice
	}

	// 5. Daily Loss Limit Circuit Breaker
	if p.DailyPnL < 0 && math.Abs(p.DailyPnL) > e.config.MaxDailyLossPct*p.Equity {
		reasons = append(reasons, fmt.Sprintf("Daily loss limit breached: %.2f%% > %.2f%%", math.Abs(p.DailyPnL)/p.Equity*100, e.config.MaxDailyLossPct*100))
	}

	// 6. Drawdown Limit Circuit Breaker
	if p.PeakEquity > 0 {
		dd := (p.PeakEquity - p.Equity) / p.PeakEquity
		if dd > e.config.MaxDrawdownPct {
			reasons = append(reasons, fmt.Sprintf("Drawdown circuit breaker triggered: %.2f%% > %.2f%%", dd*100, e.config.MaxDrawdownPct*100))
		}
	}

	// 7. Daily Orders Count Limit
	if dailyOrders >= e.config.MaxOrdersPerDay {
		reasons = append(reasons, fmt.Sprintf("Maximum daily orders limit reached (%d)", e.config.MaxOrdersPerDay))
	}

	// 8. Minimum Order Notional
	if riskNotional < e.config.MinOrderNotional {
		reasons = append(reasons, fmt.Sprintf("Order notional $%.2f is below minimum threshold $%.2f", riskNotional, e.config.MinOrderNotional))
	}

	// Compute open/pending order reservations
	resCash, _, resGross, resSymExp, resSellQty := e.computeActiveReservationsLocked(order.Symbol)

	// 9. Buy-Specific Balance and Exposure Limits (incorporating pending order reservations)
	if order.Side == models.SideBuy {
		// Minimum Cash Reserve (Cash - reservedCash - riskNotional must be >= minCash)
		minCash := e.config.MinCashReservePct * p.Equity
		availCash := p.Cash - resCash
		if (availCash - riskNotional) < minCash {
			reasons = append(reasons, fmt.Sprintf("Cash after order and reservations ($%.2f = cash $%.2f - reserved $%.2f - order $%.2f) falls below required reserve ($%.2f)", availCash-riskNotional, p.Cash, resCash, riskNotional, minCash))
		}

		// Maximum Position Sizing Limit (current + reserved + order must be <= maxSymExp)
		newSymExp := p.CurrentSymbolExposure + resSymExp + riskNotional
		maxSymExp := e.config.MaxPositionPct * p.Equity
		if newSymExp > maxSymExp {
			reasons = append(reasons, fmt.Sprintf("Target position with reservations ($%.2f = current $%.2f + reserved $%.2f + order $%.2f) exceeds max allowed position sizing ($%.2f)", newSymExp, p.CurrentSymbolExposure, resSymExp, riskNotional, maxSymExp))
		}

		// Maximum Gross Portfolio Exposure Limit (current + reserved + order must be <= maxGross)
		newGross := p.GrossExposure + resGross + riskNotional
		maxGross := e.config.MaxGrossExposurePct * p.Equity
		if newGross > maxGross {
			reasons = append(reasons, fmt.Sprintf("Gross exposure with reservations ($%.2f = current $%.2f + reserved $%.2f + order $%.2f) exceeds max allowed portfolio limit ($%.2f)", newGross, p.GrossExposure, resGross, riskNotional, maxGross))
		}
	}

	// 10. Sell-Specific Controls & Short Selling Prohibition (incorporating reserved sell qty)
	if order.Side == models.SideSell {
		if !e.allowShorting {
			pos, hasPos := e.positions[order.Symbol]
			confirmedQty := 0.0
			if hasPos {
				confirmedQty = pos.Qty
			}
			availableSellQty := confirmedQty - resSellQty
			if float64(order.Qty) > availableSellQty {
				reasons = append(reasons, fmt.Sprintf("Short selling prohibited: requested sell qty (%d) exceeds available long position (%.0f = confirmed %.0f - reserved %.0f)", order.Qty, availableSellQty, confirmedQty, resSellQty))
			}
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

	// Write-Ahead: Durably record event to journal before committing to in-memory history
	if err := e.recordEventLocked(EventOrderSubmitting, &ordCopy, nil, ordCopy.ClientOrderID, "", ""); err != nil {
		ordCopy.Status = models.OrderStatusRejected
		metrics.DefaultRegistry.IncOrdersRejected()
		return nil, models.RiskDecision{
			Approved: false,
			Order:    &ordCopy,
			Reasons:  []string{fmt.Sprintf("Execution blocked: journal persistence error: %v", err)},
			TraceID:  traceID,
		}
	}

	e.orderHistory[ordCopy.ClientOrderID] = ordCopy
	e.orderList = append(e.orderList, ordCopy)
	e.dailyOrders++

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
	case EventCancelRequested:
		if ord, ok := e.orderHistory[evt.ClientOrderID]; ok {
			ord.Status = models.OrderStatusCancelPending
			if evt.Reason != "" {
				ord.Reason = evt.Reason
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
	case EventSubmissionUnknown:
		if ord, ok := e.orderHistory[evt.ClientOrderID]; ok {
			ord.Status = models.OrderStatusSubmissionUnknown
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

// Submit performs the full order submission state machine with ambiguous failure recovery:
// CheckRisk/ReserveOrder -> SUBMITTING -> broker SubmitOrder.
// If broker returns success -> ACKNOWLEDGED.
// If broker returns confirmed rejection -> SUBMIT_FAILED.
// If broker returns ambiguous transport error (timeout, connection reset, 5xx):
//   -> SUBMISSION_UNKNOWN
//   -> query broker using SAME client_order_id:
//        - found -> ACKNOWLEDGED (or actual broker status)
//        - confirmed absent -> SUBMIT_FAILED
//        - uncertain / query fails -> remain SUBMISSION_UNKNOWN and FREEZE engine for operator reconciliation.
func (e *Engine) Submit(order *models.OrderIntent, b broker.BrokerAdapter) (*broker.BrokerOrder, models.RiskDecision, error) {
	if b == nil {
		return nil, models.RiskDecision{Approved: false, Reasons: []string{"broker adapter is nil"}}, errors.New("broker adapter is nil")
	}

	reserved, decision := e.ReserveOrder(order)
	if !decision.Approved {
		return nil, decision, fmt.Errorf("risk rejection: %v", decision.Reasons)
	}

	resp, err := b.SubmitOrder(reserved)
	if err == nil && resp != nil {
		brokerOrderID := resp.ID
		_ = e.UpdateOrderStatusAndBrokerID(order.ClientOrderID, models.OrderStatusAcknowledged, brokerOrderID)
		metrics.DefaultRegistry.IncOrdersSubmitted()
		return resp, decision, nil
	}

	// SubmitOrder returned an error. Classify into Confirmed Rejection vs Ambiguous Transport Failure.
	if !broker.IsAmbiguousTransportError(err) {
		// Confirmed rejection (e.g. 400 Bad Request, 422 Unprocessable, unconfigured)
		_ = e.UpdateOrderStatus(order.ClientOrderID, models.OrderStatusSubmitFailed, err.Error())
		return nil, decision, err
	}

	// Ambiguous transport failure (timeout, network drop, 5xx).
	// 1. Mark status as SUBMISSION_UNKNOWN and durably journal
	_ = e.UpdateOrderStatus(order.ClientOrderID, models.OrderStatusSubmissionUnknown, fmt.Sprintf("ambiguous transport failure: %v", err))

	// 2. Bounded verification: query broker using the EXACT SAME client_order_id
	queryResp, queryErr := b.GetOrder(order.ClientOrderID)
	if queryErr == nil && queryResp != nil {
		// Subcase A: Order was successfully accepted by the broker despite network failure on submit response
		var finalStatus models.OrderStatus
		switch queryResp.Status {
		case broker.BrokerOrderStatusFilled:
			finalStatus = models.OrderStatusFilled
		case broker.BrokerOrderStatusPartiallyFilled:
			finalStatus = models.OrderStatusPartiallyFilled
		case broker.BrokerOrderStatusCanceled:
			finalStatus = models.OrderStatusCancelled
		case broker.BrokerOrderStatusRejected:
			finalStatus = models.OrderStatusRejected
		default:
			finalStatus = models.OrderStatusAcknowledged
		}
		_ = e.UpdateOrderStatusAndBrokerID(order.ClientOrderID, finalStatus, queryResp.ID)
		metrics.DefaultRegistry.IncOrdersSubmitted()
		return queryResp, decision, nil
	}

	if broker.IsOrderNotFoundError(queryErr) {
		// Subcase B: Order confirmed absent on broker
		_ = e.UpdateOrderStatus(order.ClientOrderID, models.OrderStatusSubmitFailed, fmt.Sprintf("confirmed absent on broker after ambiguous submit failure (%v)", err))
		return nil, decision, fmt.Errorf("submit failed (confirmed absent on broker): %w", err)
	}

	// Subcase C: Still uncertain (e.g. query also timed out or returned error).
	// Invariant: Freeze engine immediately and require explicit reconciliation.
	freezeReason := fmt.Sprintf("unresolved ambiguous broker submission for order %s (%v); reconciliation required", order.ClientOrderID, err)
	e.FreezeWithReason(freezeReason, "oms_ambiguity_gate", "")
	return nil, decision, fmt.Errorf("ambiguous submission state unresolved (engine frozen): %w", err)
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

// RequestCancel transitions an order to CANCEL_PENDING, journals the event, and submits a cancellation request to the broker.
// Note: A cancel request is NOT a confirmed cancellation. Confirmed cancellation happens when broker confirms CANCELED.
// Late fills that occur after a cancel request are still fully processed by ApplyFill.
func (e *Engine) RequestCancel(clientOrderID string, b broker.BrokerAdapter, reason string) (*models.OrderIntent, error) {
	e.mu.Lock()

	if !e.journalReady {
		e.mu.Unlock()
		return nil, errors.New("cannot cancel order: durable journal is not ready")
	}

	ord, exists := e.orderHistory[clientOrderID]
	if !exists {
		e.mu.Unlock()
		return nil, fmt.Errorf("order not found: %s", clientOrderID)
	}

	// If already in terminal status
	if ord.Status == models.OrderStatusCancelled ||
		ord.Status == models.OrderStatusFilled ||
		ord.Status == models.OrderStatusRejected ||
		ord.Status == models.OrderStatusSubmitFailed ||
		ord.Status == models.OrderStatusExpired {
		e.mu.Unlock()
		return nil, fmt.Errorf("order %s cannot be canceled in terminal status %s", clientOrderID, ord.Status)
	}

	if ord.Status == models.OrderStatusCancelPending {
		// Idempotent: already cancel pending
		ordCopy := ord
		e.mu.Unlock()
		if b != nil {
			_ = b.CancelOrder(clientOrderID)
		}
		return &ordCopy, nil
	}

	// 1. Journal write-ahead CANCEL_REQUESTED
	if err := e.recordEventLocked(EventCancelRequested, nil, nil, clientOrderID, ord.BrokerOrderID, reason); err != nil {
		e.mu.Unlock()
		return nil, fmt.Errorf("failed to journal cancel request: %w", err)
	}

	// 2. Transition local order to CANCEL_PENDING
	ord.Status = models.OrderStatusCancelPending
	if reason != "" {
		ord.Reason = reason
	}
	ord.UpdatedAt = time.Now().UTC()
	e.orderHistory[clientOrderID] = ord
	for i := range e.orderList {
		if e.orderList[i].ClientOrderID == clientOrderID {
			e.orderList[i] = ord
			break
		}
	}
	ordCopy := ord
	e.mu.Unlock()

	// 3. Dispatch cancellation request to broker
	if b != nil {
		cancelErr := b.CancelOrder(clientOrderID)
		if cancelErr != nil {
			// Broker cancel request returned an error.
			// If broker error indicates already filled or canceled, query broker to see current state.
			queryResp, queryErr := b.GetOrder(clientOrderID)
			if queryErr == nil && queryResp != nil {
				if queryResp.Status == broker.BrokerOrderStatusFilled {
					_ = e.UpdateOrderStatus(clientOrderID, models.OrderStatusFilled, "broker confirmed filled prior to cancel")
				} else if queryResp.Status == broker.BrokerOrderStatusCanceled {
					_ = e.UpdateOrderStatus(clientOrderID, models.OrderStatusCancelled, "broker confirmed canceled")
				}
			}
			return &ordCopy, cancelErr
		}
	}

	return &ordCopy, nil
}

// ConfirmCancel confirms that an order is officially canceled by the broker and releases all reservations.
func (e *Engine) ConfirmCancel(clientOrderID string, reason string) error {
	return e.UpdateOrderStatus(clientOrderID, models.OrderStatusCancelled, reason)
}

// CancelAllOpenOrders iterates over all active/open orders in the OMS and requests cancellation on the broker.
func (e *Engine) CancelAllOpenOrders(b broker.BrokerAdapter, reason string) ([]models.OrderIntent, error) {
	e.mu.RLock()
	var openOrderIDs []string
	for _, ord := range e.orderList {
		switch ord.Status {
		case models.OrderStatusSubmitting,
			models.OrderStatusSubmissionUnknown,
			models.OrderStatusAcknowledged,
			models.OrderStatusPartiallyFilled,
			models.OrderStatusCancelPending:
			openOrderIDs = append(openOrderIDs, ord.ClientOrderID)
		}
	}
	e.mu.RUnlock()

	var canceled []models.OrderIntent
	var errs []string
	for _, id := range openOrderIDs {
		ord, err := e.RequestCancel(id, b, reason)
		if err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", id, err))
		}
		if ord != nil {
			canceled = append(canceled, *ord)
		}
	}

	if len(errs) > 0 {
		return canceled, fmt.Errorf("errors cancelling open orders: %s", strings.Join(errs, "; "))
	}
	return canceled, nil
}

