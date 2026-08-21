package broker

import (
	"fmt"
	"sync"
	"time"

	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

type PaperAdapter struct {
	mu        sync.RWMutex
	name      string
	cash      float64
	orders    map[string]BrokerOrder
	positions map[string]BrokerPosition
}

func NewPaperAdapter(name string, initialCash float64) *PaperAdapter {
	if name == "" {
		name = "paper-simulation"
	}
	return &PaperAdapter{
		name:      name,
		cash:      initialCash,
		orders:    make(map[string]BrokerOrder),
		positions: make(map[string]BrokerPosition),
	}
}

func (p *PaperAdapter) Name() string {
	return p.name
}

func (p *PaperAdapter) Kind() BrokerKind {
	return BrokerKindPaper
}

func (p *PaperAdapter) Environment() Environment {
	return EnvSimulation
}

func (p *PaperAdapter) IsConfigured() bool {
	return true
}

func (p *PaperAdapter) SubmitOrder(order *models.OrderIntent) (*BrokerOrder, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	now := time.Now().UTC()
	brokerID := fmt.Sprintf("paper-%d", now.UnixNano())

	bo := BrokerOrder{
		ID:               brokerID,
		BrokerOrderID:    brokerID,
		ClientOrderID:    order.ClientOrderID,
		Symbol:           order.Symbol,
		Side:             string(order.Side),
		Qty:              order.Qty,
		RequestedQty:     float64(order.Qty),
		FilledQty:        order.Qty, // instantaneous simulated paper fill
		FilledQtyFloat:   float64(order.Qty),
		Status:           BrokerOrderStatusFilled,
		RawStatus:        "filled",
		LimitPrice:       order.ReferencePrice,
		AvgPrice:         order.ReferencePrice,
		AverageFillPrice: order.ReferencePrice,
		CreatedAt:        now,
		UpdatedAt:        now,
	}

	p.orders[order.ClientOrderID] = bo

	// Update simulated cash and positions
	cost := float64(order.Qty) * order.ReferencePrice
	if order.Side == models.SideBuy {
		p.cash -= cost
		pos := p.positions[order.Symbol]
		pos.Symbol = order.Symbol
		pos.Qty += float64(order.Qty)
		pos.CostBasis += cost
		pos.MarketValue = pos.Qty * order.ReferencePrice
		p.positions[order.Symbol] = pos
	} else if order.Side == models.SideSell {
		p.cash += cost
		pos := p.positions[order.Symbol]
		pos.Qty -= float64(order.Qty)
		pos.MarketValue = pos.Qty * order.ReferencePrice
		p.positions[order.Symbol] = pos
	}

	return &bo, nil
}

func (p *PaperAdapter) CancelOrder(clientOrderID string) error {
	p.mu.Lock()
	defer p.mu.Unlock()

	ord, exists := p.orders[clientOrderID]
	if !exists {
		return fmt.Errorf("order not found: %s", clientOrderID)
	}
	ord.Status = BrokerOrderStatusCanceled
	ord.RawStatus = "canceled"
	ord.UpdatedAt = time.Now().UTC()
	p.orders[clientOrderID] = ord
	return nil
}

func (p *PaperAdapter) GetOrder(clientOrderID string) (*BrokerOrder, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	ord, exists := p.orders[clientOrderID]
	if !exists {
		return nil, fmt.Errorf("order not found: %s", clientOrderID)
	}
	return &ord, nil
}

func (p *PaperAdapter) ListOrders() ([]BrokerOrder, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	var list []BrokerOrder
	for _, ord := range p.orders {
		list = append(list, ord)
	}
	return list, nil
}

func (p *PaperAdapter) ListPositions() ([]BrokerPosition, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	var list []BrokerPosition
	for _, pos := range p.positions {
		if pos.Qty != 0 {
			list = append(list, pos)
		}
	}
	return list, nil
}

func (p *PaperAdapter) GetAccountState() (*AccountState, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	posVal := 0.0
	for _, pos := range p.positions {
		posVal += pos.MarketValue
	}

	return &AccountState{
		Cash:        p.cash,
		Equity:      p.cash + posVal,
		BuyingPower: p.cash * 2.0,
		Currency:    "USD",
	}, nil
}

func (p *PaperAdapter) GetHealth() Health {
	return Health{
		Ready:         true,
		Connected:     true,
		Configured:    true,
		Broker:        BrokerKindPaper,
		Name:          p.name,
		Environment:   EnvSimulation,
		Message:       "Internal simulation engine running with instantaneous execution",
		LastCheckedAt: time.Now().UTC(),
	}
}

func (p *PaperAdapter) GetBrokerSnapshot() (*reconciliation.BrokerState, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	now := time.Now().UTC()
	reconOrders := make(map[string]reconciliation.OrderState)
	for clientID, ord := range p.orders {
		reconOrders[clientID] = reconciliation.OrderState{
			ClientOrderID: ord.ClientOrderID,
			BrokerOrderID: ord.ID,
			Symbol:        ord.Symbol,
			Side:          ord.Side,
			RequestedQty:  ord.Qty,
			FilledQty:     ord.FilledQty,
			Status:        string(ord.Status),
			CreatedAt:     ord.CreatedAt,
			UpdatedAt:     ord.UpdatedAt,
		}
	}

	reconPositions := make(map[string]reconciliation.PositionState)
	posVal := 0.0
	for sym, pos := range p.positions {
		if pos.Qty != 0 {
			reconPositions[sym] = reconciliation.PositionState{
				Symbol:      pos.Symbol,
				Qty:         pos.Qty,
				MarketValue: pos.MarketValue,
				CostBasis:   pos.CostBasis,
			}
			posVal += pos.MarketValue
		}
	}

	return &reconciliation.BrokerState{
		Orders:    reconOrders,
		Positions: reconPositions,
		Cash:      p.cash,
		Equity:    p.cash + posVal,
		Timestamp: now,
	}, nil
}
