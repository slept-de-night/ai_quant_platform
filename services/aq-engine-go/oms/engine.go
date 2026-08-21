package oms

import (
	"errors"
	"fmt"
	"math"
	"sync"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/models"
)

type Engine struct {
	mu           sync.RWMutex
	portfolio    models.PortfolioState
	config       models.RiskConfig
	orderHistory map[string]models.OrderIntent
	orderList    []models.OrderIntent
	dailyOrders  int
	lastResetDay string
	isFrozen     bool
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
		lastResetDay: time.Now().UTC().Format("2006-01-02"),
		isFrozen:     false,
	}
}

func (e *Engine) Freeze() {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.isFrozen = true
	e.portfolio.IsFrozen = true
}

func (e *Engine) Unfreeze() {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.isFrozen = false
	e.portfolio.IsFrozen = false
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

func (e *Engine) UpdateOrderStatus(clientOrderID string, status models.OrderStatus, reasons ...string) {
	e.UpdateOrderStatusAndBrokerID(clientOrderID, status, "", reasons...)
}

func (e *Engine) UpdateOrderStatusAndBrokerID(clientOrderID string, status models.OrderStatus, brokerOrderID string, reasons ...string) {
	e.mu.Lock()
	defer e.mu.Unlock()

	if ord, exists := e.orderHistory[clientOrderID]; exists {
		ord.Status = status
		if brokerOrderID != "" {
			ord.BrokerOrderID = brokerOrderID
		}
		if len(reasons) > 0 && reasons[0] != "" {
			ord.Reason = reasons[0]
		}
		e.orderHistory[clientOrderID] = ord
		for i := range e.orderList {
			if e.orderList[i].ClientOrderID == clientOrderID {
				e.orderList[i].Status = status
				if brokerOrderID != "" {
					e.orderList[i].BrokerOrderID = brokerOrderID
				}
				if len(reasons) > 0 && reasons[0] != "" {
					e.orderList[i].Reason = reasons[0]
				}
				break
			}
		}
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
	return resp, decision, nil
}
