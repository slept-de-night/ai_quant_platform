package market

import (
	"sync"

	"aq-engine-go/models"
)

type Gateway struct {
	mu          sync.RWMutex
	latestTicks map[string]models.MarketTick
	subscribers map[string][]chan models.MarketTick
}

func NewGateway() *Gateway {
	return &Gateway{
		latestTicks: make(map[string]models.MarketTick),
		subscribers: make(map[string][]chan models.MarketTick),
	}
}

func (g *Gateway) PublishTick(tick models.MarketTick) {
	g.mu.Lock()
	defer g.mu.Unlock()

	g.latestTicks[tick.Symbol] = tick

	// Broadcast non-blockingly to subscribers
	if subs, ok := g.subscribers[tick.Symbol]; ok {
		for _, ch := range subs {
			select {
			case ch <- tick:
			default:
				// Channel full, drop tick to avoid backpressure
			}
		}
	}
}

func (g *Gateway) GetLatestTick(symbol string) (models.MarketTick, bool) {
	g.mu.RLock()
	defer g.mu.RUnlock()

	tick, ok := g.latestTicks[symbol]
	if !ok {
		return models.MarketTick{
			Symbol: symbol,
		}, false
	}
	return tick, true
}

func (g *Gateway) GetAllTicks() map[string]models.MarketTick {
	g.mu.RLock()
	defer g.mu.RUnlock()

	out := make(map[string]models.MarketTick, len(g.latestTicks))
	for k, v := range g.latestTicks {
		out[k] = v
	}
	return out
}
