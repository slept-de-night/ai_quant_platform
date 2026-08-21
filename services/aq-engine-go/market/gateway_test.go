package market

import (
	"testing"
	"time"

	"aq-engine-go/models"
)

func TestGatewayGetLatestTickMissingReturnsUnavailable(t *testing.T) {
	gw := NewGateway()

	// Query unseeded symbol
	tick, found := gw.GetLatestTick("NVDA")
	if found {
		t.Fatalf("expected found=false for unseeded symbol, got true")
	}
	if tick.Price != 0 {
		t.Fatalf("expected Price=0 for unseeded symbol, got %f (must never fabricate price)", tick.Price)
	}
	if tick.Symbol != "NVDA" {
		t.Fatalf("expected Symbol=NVDA, got %s", tick.Symbol)
	}
}

func TestGatewayPublishAndQueryDemoTick(t *testing.T) {
	gw := NewGateway()

	demoTick := models.MarketTick{
		Symbol:      "SPY",
		Price:       512.45,
		Volume:      4500000,
		Timestamp:   time.Now().UTC(),
		Source:      "demo",
		IsSimulated: true,
	}
	gw.PublishTick(demoTick)

	retrieved, found := gw.GetLatestTick("SPY")
	if !found {
		t.Fatalf("expected found=true for published tick")
	}
	if retrieved.Price != 512.45 {
		t.Fatalf("expected Price=512.45, got %f", retrieved.Price)
	}
	if retrieved.Source != "demo" || !retrieved.IsSimulated {
		t.Fatalf("expected Source=demo and IsSimulated=true, got Source=%s, IsSimulated=%v", retrieved.Source, retrieved.IsSimulated)
	}
}
