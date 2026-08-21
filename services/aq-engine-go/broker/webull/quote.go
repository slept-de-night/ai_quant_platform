package webull

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"net/url"
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
	Symbol     string `json:"symbol"`
	Bid        string `json:"bid"`
	Ask        string `json:"ask"`
	Last       string `json:"last"`
	Volume     string `json:"volume"`
	QuoteTime  string `json:"quote_time"`
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

	query := url.Values{}
	query.Set("symbol", symbol)

	code, body, err := client.Execute(ctx, "GET", "/api/v1/market/quote", query, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch quote for %s (HTTP %d): %w", symbol, code, err)
	}

	var raw rawQuoteResponse
	if err := json.Unmarshal(body, &raw); err != nil {
		return nil, fmt.Errorf("failed to parse quote JSON: %w", err)
	}

	bid := parseFloatSafe(raw.Bid)
	ask := parseFloatSafe(raw.Ask)
	last := parseFloatSafe(raw.Last)
	vol := parseFloatSafe(raw.Volume)

	ts := time.Now().UTC()
	if raw.QuoteTime != "" {
		if t, err := time.Parse(time.RFC3339, raw.QuoteTime); err == nil {
			ts = t
		}
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
