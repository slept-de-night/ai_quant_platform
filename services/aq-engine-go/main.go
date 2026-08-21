package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"aq-engine-go/auth"
	"aq-engine-go/broker"
	"aq-engine-go/market"
	"aq-engine-go/metrics"
	"aq-engine-go/models"
	"aq-engine-go/oms"
	"aq-engine-go/reconciliation"
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
	webullKey := os.Getenv("WEBULL_APP_KEY")
	webullSecret := os.Getenv("WEBULL_APP_SECRET")
	webullAccount := os.Getenv("WEBULL_ACCOUNT_ID")

	// Initialize subsystems
	riskCfg := models.DefaultRiskConfig()
	engine := oms.NewEngine(initialEquity, riskCfg)
	gateway := market.NewGateway()

	journalPath := os.Getenv("OMS_JOURNAL_PATH")
	if journalPath == "" {
		journalPath = "data/oms_journal.jsonl"
	}
	journal, err := oms.NewJournal(journalPath)
	if err != nil {
		log.Printf("[JOURNAL WARNING] Could not initialize journal %s: %v", journalPath, err)
	} else {
		engine.SetJournal(journal)
		replayed, err := journal.Replay(engine)
		if err != nil {
			log.Printf("[JOURNAL REPLAY ERROR] Replay failed: %v. Engine frozen.", err)
		} else if replayed > 0 {
			log.Printf("[JOURNAL REPLAY] Successfully recovered %d events from %s", replayed, journalPath)
		}
	}

	// Initialize Pluggable Broker Registry
	brokerReg := broker.NewRegistry()
	paperAdapter := broker.NewPaperAdapter("paper-simulation", initialEquity)
	webullAdapter := broker.NewWebullAdapter("webull-main", webullKey, webullSecret, webullAccount, true)
	alpacaAdapter := broker.NewAlpacaAdapter("alpaca-paper", alpacaKey, alpacaSecret, true)

	// Safe default startup broker is paper
	brokerReg.Register(paperAdapter)
	brokerReg.Register(alpacaAdapter)
	brokerReg.Register(webullAdapter)

	execBroker := strings.ToLower(strings.TrimSpace(os.Getenv("EXECUTION_BROKER")))
	switch execBroker {
	case "alpaca":
		if alpacaKey == "" || alpacaSecret == "" {
			log.Printf("[BROKER WARNING] EXECUTION_BROKER=alpaca requested but credentials missing; operating in safe paper simulation fallback")
		}
		_ = brokerReg.SetActive("alpaca-paper")
		log.Printf("[BROKER POSTURE] Active broker set to Alpaca Paper Adapter")
	case "webull":
		if webullKey == "" || webullSecret == "" {
			log.Printf("[BROKER WARNING] EXECUTION_BROKER=webull requested but credentials missing; operating in safe paper simulation fallback")
		}
		_ = brokerReg.SetActive("webull-main")
		log.Printf("[BROKER POSTURE] Active broker set to Webull Main Adapter")
	default:
		_ = brokerReg.SetActive("paper-simulation")
		log.Printf("[BROKER POSTURE] Active broker set to default Paper Simulation Adapter")
	}

	// Seed some baseline market ticks
	gateway.PublishTick(models.MarketTick{Symbol: "SPY", Price: 512.45, Volume: 4500000, Timestamp: time.Now().UTC()})
	gateway.PublishTick(models.MarketTick{Symbol: "NVDA", Price: 128.50, Volume: 12000000, Timestamp: time.Now().UTC()})
	gateway.PublishTick(models.MarketTick{Symbol: "QQQ", Price: 445.20, Volume: 3200000, Timestamp: time.Now().UTC()})

	// Startup Reconciliation Gate
	activeB, _ := brokerReg.GetActive()
	if activeB != nil {
		if snap, err := activeB.GetBrokerSnapshot(); err == nil {
			startReconciler := reconciliation.NewReconciler(0.001, 1.0, 5*time.Minute)
			localSnap := engine.ConstructLocalSnapshot()
			diff := startReconciler.Reconcile(localSnap, *snap)
			if diff.HasCritical {
				engine.Freeze()
				log.Printf("[STARTUP GATE] Critical reconciliation discrepancy detected. OMS initial state: FROZEN (%d discrepancies)", diff.TotalCount)
			} else {
				log.Printf("[STARTUP GATE] Startup reconciliation clean. OMS initial state: READY")
			}
		}
	}

	mux := setupRouter(engine, brokerReg, gateway)

	authToken := os.Getenv("AUTH_TOKEN")
	if authToken == "" {
		authToken = os.Getenv("ENGINE_API_KEY")
	}
	authRequired := os.Getenv("AUTH_REQUIRED") == "true"
	authMw := auth.Middleware(authToken, authRequired)

	handler := metrics.DefaultRegistry.Middleware(authMw(mux))

	log.Printf("Starting Go High-Performance Execution Engine on :%s", port)
	if err := http.ListenAndServe(":"+port, handler); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

func setupRouter(engine *oms.Engine, brokerReg *broker.Registry, gateway *market.Gateway) *http.ServeMux {
	mux := http.NewServeMux()

	// 0. Observability & Operational Metrics
	mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		w.Write([]byte(metrics.DefaultRegistry.PrometheusFormat()))
	})

	mux.HandleFunc("GET /api/v1/metrics", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(metrics.DefaultRegistry.Snapshot())
	})

	// 1. Health & Diagnostics
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		activeB, _ := brokerReg.GetActive()
		activeHealth := broker.Health{}
		if activeB != nil {
			activeHealth = activeB.GetHealth()
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":         "healthy",
			"engine":         "aq-engine-go",
			"version":        "1.3.0-enterprise",
			"uptime_seconds": time.Since(startTime).Seconds(),
			"active_broker":  activeHealth.Name,
			"broker_kind":    activeHealth.Broker,
			"execution_mode": activeHealth.Environment,
			"is_frozen":      engine.IsFrozen(),
			"brokers":        brokerReg.List(),
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

	// 3. Sub-millisecond Pure Risk Check
	mux.HandleFunc("POST /api/v1/risk/check", func(w http.ResponseWriter, r *http.Request) {
		var order models.OrderIntent
		if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
			http.Error(w, fmt.Sprintf("invalid request payload: %v", err), http.StatusBadRequest)
			return
		}

		decision := engine.CheckRisk(&order)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(decision)
	})

	// 4. Order Execution (Risk Check + Atomically Reserve SUBMITTING + Pluggable Broker Submit)
	mux.HandleFunc("POST /api/v1/orders/submit", func(w http.ResponseWriter, r *http.Request) {
		var order models.OrderIntent
		if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
			http.Error(w, fmt.Sprintf("invalid request payload: %v", err), http.StatusBadRequest)
			return
		}

		// Dispatch to Active Pluggable Broker Adapter (Webull / Alpaca / Paper)
		activeBroker, err := brokerReg.GetActive()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		resp, decision, err := engine.Submit(&order, activeBroker)
		if err != nil {
			if !decision.Approved {
				w.Header().Set("Content-Type", "application/json")
				json.NewEncoder(w).Encode(map[string]interface{}{
					"submitted": false,
					"decision":  decision,
				})
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"submitted": false,
				"error":     err.Error(),
				"decision":  decision,
			})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"submitted":       true,
			"decision":        decision,
			"broker_response": resp,
			"broker_name":     activeBroker.Name(),
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

	// 10. Automated Broker Reconciliation Engine
	reconciler := reconciliation.NewReconciler(0.001, 1.0, 5*time.Minute)
	mux.HandleFunc("POST /api/v1/reconciliation/run", func(w http.ResponseWriter, r *http.Request) {
		localState := engine.ConstructLocalSnapshot()

		activeB, err := brokerReg.GetActive()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		brokerSnapshot, err := activeB.GetBrokerSnapshot()
		if err != nil {
			http.Error(w, fmt.Sprintf("failed to get broker snapshot: %v", err), http.StatusInternalServerError)
			return
		}

		diff := reconciler.Reconcile(localState, *brokerSnapshot)
		metrics.DefaultRegistry.AddReconciliationDiscrepancies(uint64(diff.TotalCount))
		if diff.HasCritical {
			engine.Freeze()
			log.Printf("[RECONCILIATION ALERT] Critical discrepancy detected. OMS frozen in FROZEN_RECONCILIATION (%d discrepancies)", diff.TotalCount)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(diff)
	})

	// 11. Pluggable Broker Management Endpoints
	mux.HandleFunc("GET /api/v1/brokers/health", func(w http.ResponseWriter, r *http.Request) {
		summary, err := brokerReg.GetHealthSummary()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(summary)
	})

	mux.HandleFunc("GET /api/v1/brokers", func(w http.ResponseWriter, r *http.Request) {
		activeB, _ := brokerReg.GetActive()
		activeName := ""
		if activeB != nil {
			activeName = activeB.Name()
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"active":  activeName,
			"brokers": brokerReg.List(),
		})
	})

	mux.HandleFunc("POST /api/v1/brokers/select", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Name string `json:"name"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid request body", http.StatusBadRequest)
			return
		}

		if err := brokerReg.SetActive(req.Name); err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		activeB, _ := brokerReg.GetActive()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "selected",
			"active": activeB.Name(),
			"health": activeB.GetHealth(),
		})
	})

	return mux
}



