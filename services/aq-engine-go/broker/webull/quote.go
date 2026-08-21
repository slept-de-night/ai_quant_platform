package webull

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"strconv"
	"time"

	"aq-engine-go/market"
	"aq-engine-go/models"
)

var (
	ErrStaleQuote      = errors.New("market quote exceeds maximum staleness threshold (> 60s)")
	ErrInvalidQuote    = errors.New("invalid or empty market quote data")
	ErrNBBODeviation   = errors.New("order price deviates beyond maximum allowed NBBO threshold (> 5%)")
)

// WebullQuote represents a normalized market quote from Webull OpenAPI.
type WebullQuote struct {
	Symbol    string    `json:"symbol"`
	BidPrice  float64   `json:"bid_price"`
	AskPrice  float64   `json:"ask_price"`
	LastPrice float64   `json:"last_price"`
	Volume    float64   `json:"volume"`
	Timestamp time.Time `json:"timestamp"`
}

type rawQuoteResponse struct {
	Symbol        string `json:"symbol"`
	LastTradeTime string `json:"last_trade_time"`
	Price         string `json:"price"`
	Bid           string `json:"bid"`
	Ask           string `json:"ask"`
	BidSize       string `json:"bid_size"`
	AskSize       string `json:"ask_size"`
	Volume        string `json:"volume"`
}

type rawSnapshotRequest struct {
	Symbols  []string `json:"symbols"`
	Category string   `json:"category"`
}

// FetchQuote queries the Webull OpenAPI quote endpoint for a symbol.
func FetchQuote(ctx context.Context, client *Client, symbol string, maxStaleness time.Duration) (*WebullQuote, error) {
	if client == nil {
		return nil, errors.New("webull client cannot be nil")
	}
	if symbol == "" {
		return nil, errors.New("symbol cannot be empty")
	}
	if maxStaleness <= 0 {
		maxStaleness = 60 * time.Second
	}

	req := rawSnapshotRequest{Symbols: []string{symbol}, Category: "US_STOCK"}
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal snapshot request: %w", err)
	}
	code, body, err := client.Execute(ctx, "POST", EndpointMarketSnapshots, nil, reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch quote for %s (HTTP %d): %w", symbol, code, err)
	}

	var rawItems []rawQuoteResponse
	if err := json.Unmarshal(body, &rawItems); err != nil {
		return nil, fmt.Errorf("failed to parse quote JSON: %w", err)
	}

	var raw rawQuoteResponse
	found := false
	for _, item := range rawItems {
		if item.Symbol == symbol {
			raw = item
			found = true
			break
		}
	}
	if !found {
		return nil, fmt.Errorf("%w: symbol %s absent from snapshot list", ErrInvalidQuote, symbol)
	}

	bid := parseFloatSafe(raw.Bid)
	ask := parseFloatSafe(raw.Ask)
	last := parseFloatSafe(raw.Price)
	vol := parseFloatSafe(raw.Volume)

	// Webull snapshot timestamps are milliseconds since Unix epoch; never fall back to local time.
	ts := time.UnixMilli(0)
	if raw.LastTradeTime != "" {
		t, err := strconv.Atoi(raw.LastTradeTime)
		if err != nil || t <= 0 {
			return nil, fmt.Errorf("malformed authoritative quote timestamp for %s: %q", symbol, raw.LastTradeTime)
		}
		ts = time.UnixMilli(int64(t))
	}

	// Staleness validation
	if time.Since(ts) > maxStaleness {
		return nil, fmt.Errorf("%w: age %v > allowed %v", ErrStaleQuote, time.Since(ts).Round(time.Millisecond), maxStaleness)
	}

	if last <= 0 && (bid <= 0 || ask <= 0) {
		return nil, ErrInvalidQuote
	}

	if last <= 0 && bid > 0 && ask > 0 {
		last = (bid + ask) / 2.0
	}

	return &WebullQuote{
		Symbol:    symbol,
		BidPrice:  bid,
		AskPrice:  ask,
		LastPrice: last,
		Volume:    vol,
		Timestamp: ts,
	}, nil
}

// ValidateNBBODeviation checks whether the intended order price is within the allowed deviation of NBBO.
func ValidateNBBODeviation(orderPrice float64, quote *WebullQuote, maxDeviationPct float64) error {
	if orderPrice <= 0 {
		return errors.New("order price must be positive for sanity validation")
	}
	if quote == nil {
		return ErrInvalidQuote
	}
	if maxDeviationPct <= 0 {
		maxDeviationPct = 0.05 // 5% default
	}

	refPrice := quote.LastPrice
	if quote.BidPrice > 0 && quote.AskPrice > 0 {
		refPrice = (quote.BidPrice + quote.AskPrice) / 2.0
	}

	if refPrice <= 0 {
		return ErrInvalidQuote
	}

	deviation := math.Abs(orderPrice-refPrice) / refPrice
	if deviation > maxDeviationPct {
		return fmt.Errorf("%w: order price $%.2f deviates %.2f%% from NBBO benchmark $%.2f (max allowed: %.2f%%)",
			ErrNBBODeviation, orderPrice, deviation*100, refPrice, maxDeviationPct*100)
	}

	return nil
}

// PublishToGateway updates the central market gateway with the fresh quote.
func PublishToGateway(quote *WebullQuote, gateway *market.Gateway) {
	if quote == nil || gateway == nil {
		return
	}

	tick := models.MarketTick{
		Symbol:      quote.Symbol,
		Price:       quote.LastPrice,
		Volume:      quote.Volume,
		Timestamp:   quote.Timestamp,
		Source:      "webull_openapi",
		IsSimulated: false,
	}

	gateway.PublishTick(tick)
}
