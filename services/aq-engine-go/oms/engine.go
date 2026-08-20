package oms

import (
	"fmt"
	"math"
	"sync"
	"time"

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

func (e *Engine) UpdateOrderStatus(clientOrderID string, status models.OrderStatus) {
	e.mu.Lock()
	defer e.mu.Unlock()

	if ord, exists := e.orderHistory[clientOrderID]; exists {
		ord.Status = status
		e.orderHistory[clientOrderID] = ord
		for i := range e.orderList {
			if e.orderList[i].ClientOrderID == clientOrderID {
				e.orderList[i].Status = status
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

// EvaluateRisk performs deterministic sub-millisecond safety validation
func (e *Engine) EvaluateRisk(order *models.OrderIntent) models.RiskDecision {
	e.mu.Lock()
	defer e.mu.Unlock()

	var reasons []string
	traceID := order.TraceID

	// 1. Emergency Kill Switch / Freeze Check
	if e.isFrozen {
		order.Status = models.OrderStatusRejected
		return models.RiskDecision{
			Approved: false,
			Order:    order,
			Reasons:  []string{"Emergency Kill Switch Active: Firm-wide trading is currently FROZEN"},
			TraceID:  traceID,
		}
	}

	// 2. Idempotency Check
	if _, exists := e.orderHistory[order.ClientOrderID]; exists {
		order.Status = models.OrderStatusRejected
		return models.RiskDecision{
			Approved: false,
			Order:    order,
			Reasons:  []string{fmt.Sprintf("Duplicate client_order_id blocked: %s", order.ClientOrderID)},
			TraceID:  traceID,
		}
	}

	p := e.portfolio

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
	if e.dailyOrders >= e.config.MaxOrdersPerDay {
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

	if len(reasons) > 0 {
		order.Status = models.OrderStatusRejected
		return models.RiskDecision{
			Approved: false,
			Order:    order,
			Reasons:  reasons,
			TraceID:  traceID,
		}
	}

	// Reserve and record order atomically
	order.CreatedAt = time.Now().UTC()
	order.Status = models.OrderStatusApproved
	e.orderHistory[order.ClientOrderID] = *order
	e.orderList = append(e.orderList, *order)
	e.dailyOrders++

	return models.RiskDecision{
		Approved: true,
		Order:    order,
		Reasons:  nil,
		TraceID:  traceID,
	}
}

