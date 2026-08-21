package webull

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"aq-engine-go/market"
)

// TestFetchQuote_ParsesValidQuote verifies quote parsing and deserialization.
func TestFetchQuote_ParsesValidQuote(t *testing.T) {
	now := time.Now().UTC()
	freshMs := int64(now.Unix()) * 1000
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/market-data/stocks/snapshots/list" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`[{
			"symbol": "AAPL",
			"price": "150.15",
			"ask": "150.20",
			"bid": "150.10",
			"volume": "500000",
			"last_trade_time": "` + fmt.Sprintf("%d", freshMs) + `"
		}]`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_key",
		AppSecret:   "wb_secret",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	quote, err := FetchQuote(context.Background(), client, "AAPL", 60*time.Second)
	if err != nil {
		t.Fatalf("FetchQuote failed: %v", err)
	}

	if quote.Symbol != "AAPL" || quote.BidPrice != 150.10 || quote.AskPrice != 150.20 || quote.LastPrice != 150.15 || quote.Volume != 500000 {
		t.Fatalf("Parsed quote mismatch: %+v", quote)
	}
}

// TestFetchQuote_StaleQuoteRejected verifies that stale quotes older than threshold fail closed.
func TestFetchQuote_StaleQuoteRejected(t *testing.T) {
	stale := time.Now().UTC().Add(-5 * time.Minute)
	staleMs := int64(stale.Unix()) * 1000
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/market-data/stocks/snapshots/list" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`[{
			"symbol": "AAPL",
			"price": "150.15",
			"ask": "150.20",
			"bid": "150.10",
			"volume": "500000",
			"last_trade_time": "` + fmt.Sprintf("%d", staleMs) + `"
		}]`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_key",
		AppSecret:   "wb_secret",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds, WithBaseURL(server.URL))
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	_, err = FetchQuote(context.Background(), client, "AAPL", 60*time.Second)
	if err == nil {
		t.Fatalf("Expected error for stale quote")
	}

	if !errors.Is(err, ErrStaleQuote) {
		t.Fatalf("Expected ErrStaleQuote, got: %v", err)
	}
}

// TestValidateNBBODeviation_AcceptsWithinThreshold verifies that orders within 5% deviation pass sanity checks.
func TestValidateNBBODeviation_AcceptsWithinThreshold(t *testing.T) {
	quote := &WebullQuote{
		Symbol:    "NVDA",
		BidPrice:  100.0,
		AskPrice:  100.0,
		LastPrice: 100.0,
		Timestamp: time.Now().UTC(),
	}

	// 103.0 is 3.0% deviation <= 5.0% threshold -> must PASS
	err := ValidateNBBODeviation(103.0, quote, 0.05)
	if err != nil {
		t.Fatalf("Expected price 103.0 to pass NBBO sanity check, got: %v", err)
	}

	// 97.0 is 3.0% deviation <= 5.0% threshold -> must PASS
	err = ValidateNBBODeviation(97.0, quote, 0.05)
	if err != nil {
		t.Fatalf("Expected price 97.0 to pass NBBO sanity check, got: %v", err)
	}
}

// TestValidateNBBODeviation_RejectsExcessiveDeviation verifies that orders exceeding 5% deviation are rejected.
func TestValidateNBBODeviation_RejectsExcessiveDeviation(t *testing.T) {
	quote := &WebullQuote{
		Symbol:    "NVDA",
		BidPrice:  100.0,
		AskPrice:  100.0,
		LastPrice: 100.0,
		Timestamp: time.Now().UTC(),
	}

	// 108.0 is 8.0% deviation > 5.0% threshold -> must FAIL
	err := ValidateNBBODeviation(108.0, quote, 0.05)
	if err == nil {
		t.Fatalf("Expected 108.0 to fail NBBO sanity check")
	}
	if !errors.Is(err, ErrNBBODeviation) {
		t.Fatalf("Expected ErrNBBODeviation, got: %v", err)
	}

	// 92.0 is 8.0% deviation > 5.0% threshold -> must FAIL
	err = ValidateNBBODeviation(92.0, quote, 0.05)
	if err == nil {
		t.Fatalf("Expected 92.0 to fail NBBO sanity check")
	}
	if !errors.Is(err, ErrNBBODeviation) {
		t.Fatalf("Expected ErrNBBODeviation, got: %v", err)
	}
}

// TestPublishToGateway verifies gateway population.
func TestPublishToGateway(t *testing.T) {
	gw := market.NewGateway()
	now := time.Now().UTC()
	quote := &WebullQuote{
		Symbol:    "SPY",
		BidPrice:  500.10,
		AskPrice:  500.20,
		LastPrice: 500.15,
		Volume:    1000000,
		Timestamp: now,
	}

	PublishToGateway(quote, gw)

	tick, ok := gw.GetLatestTick("SPY")
	if !ok {
		t.Fatalf("Expected SPY tick in gateway")
	}
	if tick.Price != 500.15 || tick.Volume != 1000000 || tick.Source != "webull_openapi" {
		t.Fatalf("Gateway tick mismatch: %+v", tick)
	}
}
