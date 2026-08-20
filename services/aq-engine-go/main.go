package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/market"
	"aq-engine-go/models"
	"aq-engine-go/oms"
)

var startTime = time.Now()

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	initialEquity := 100000.0
	if eqStr := os.Getenv("STARTING_EQUITY"); eqStr != "" {
		if eq, err := strconv.ParseFloat(eqStr, 64); err == nil {
			initialEquity = eq
		}
	}

	alpacaKey := os.Getenv("ALPACA_API_KEY")
	alpacaSecret := os.Getenv("ALPACA_SECRET_KEY")

	// Initialize subsystems
	riskCfg := models.DefaultRiskConfig()
	engine := oms.NewEngine(initialEquity, riskCfg)
	gateway := market.NewGateway()
	alpacaBroker := broker.NewAlpacaPaperClient(alpacaKey, alpacaSecret)

	// Seed some baseline market ticks
	gateway.PublishTick(models.MarketTick{Symbol: "SPY", Price: 512.45, Volume: 4500000, Timestamp: time.Now().UTC()})
	gateway.PublishTick(models.MarketTick{Symbol: "NVDA", Price: 128.50, Volume: 12000000, Timestamp: time.Now().UTC()})
	gateway.PublishTick(models.MarketTick{Symbol: "QQQ", Price: 445.20, Volume: 3200000, Timestamp: time.Now().UTC()})

	mux := http.NewServeMux()

	// 1. Health & Diagnostics
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":            "healthy",
			"engine":            "aq-engine-go",
			"version":           "1.2.0-core",
			"uptime_seconds":    time.Since(startTime).Seconds(),
			"alpaca_configured": alpacaBroker.IsConfigured(),
			"execution_mode":    "PAPER_ONLY",
			"is_frozen":         engine.IsFrozen(),
		})
	})


	// 2. Portfolio State
	mux.HandleFunc("GET /api/v1/portfolio", func(w http.ResponseWriter, r *http.Request) {
		symbol := r.URL.Query().Get("symbol")
		if symbol == "" {
			symbol = "SPY"
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(engine.GetPortfolio(symbol))
	})

	// 3. Sub-millisecond Risk Check
	mux.HandleFunc("POST /api/v1/risk/check", func(w http.ResponseWriter, r *http.Request) {
		var order models.OrderIntent
		if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
			http.Error(w, fmt.Sprintf("invalid request payload: %v", err), http.StatusBadRequest)
			return
		}

		decision := engine.EvaluateRisk(&order)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(decision)
	})

	// 4. Order Execution (Risk Check + Alpaca Paper Submit)
	mux.HandleFunc("POST /api/v1/orders/submit", func(w http.ResponseWriter, r *http.Request) {
		var order models.OrderIntent
		if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
			http.Error(w, fmt.Sprintf("invalid request payload: %v", err), http.StatusBadRequest)
			return
		}

		// Fast deterministic in-memory risk check
		decision := engine.EvaluateRisk(&order)
		if !decision.Approved {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]interface{}{
				"submitted": false,
				"decision":  decision,
			})
			return
		}

		// Dispatch to Alpaca Paper Broker
		resp, err := alpacaBroker.SubmitOrder(&order)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"submitted": false,
				"error":     err.Error(),
			})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"submitted":       true,
			"decision":        decision,
			"broker_response": resp,
		})
	})

	// 5. Market Tick Query
	mux.HandleFunc("GET /api/v1/market/tick", func(w http.ResponseWriter, r *http.Request) {
		symbol := r.URL.Query().Get("symbol")
		if symbol == "" {
			symbol = "SPY"
		}
		tick, found := gateway.GetLatestTick(symbol)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"found": found,
			"tick":  tick,
		})
	})

	// 6. Market Tick Ingestion
	mux.HandleFunc("POST /api/v1/market/tick", func(w http.ResponseWriter, r *http.Request) {
		var tick models.MarketTick
		if err := json.NewDecoder(r.Body).Decode(&tick); err != nil {
			http.Error(w, "invalid tick format", http.StatusBadRequest)
			return
		}
		if tick.Timestamp.IsZero() {
			tick.Timestamp = time.Now().UTC()
		}
		gateway.PublishTick(tick)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "accepted",
			"symbol": tick.Symbol,
			"price":  tick.Price,
		})
	})

	// 7. Emergency Global Kill Switch

	mux.HandleFunc("POST /api/v1/risk/kill", func(w http.ResponseWriter, r *http.Request) {
		engine.Freeze()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":    "frozen",
			"is_frozen": true,
			"message":   "Emergency Kill Switch ENGAGED: All new order submissions are BLOCKED",
			"timestamp": time.Now().UTC(),
		})
	})

	// 8. Resume / Unfreeze Execution
	mux.HandleFunc("POST /api/v1/risk/unfreeze", func(w http.ResponseWriter, r *http.Request) {
		engine.Unfreeze()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":    "active",
			"is_frozen": false,
			"message":   "Execution RESUMED: Pre-trade risk gateway is ACTIVE",
			"timestamp": time.Now().UTC(),
		})
	})

	// 9. Event-Sourced Order History Query
	mux.HandleFunc("GET /api/v1/orders/history", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"count":  len(engine.GetOrderHistory()),
			"orders": engine.GetOrderHistory(),
		})
	})

	log.Printf("Starting Go High-Performance Execution Engine on :%s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

