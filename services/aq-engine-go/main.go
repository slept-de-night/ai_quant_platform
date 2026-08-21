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

func computeReadiness(engine *oms.Engine, brokerReg *broker.Registry, gateway *market.Gateway, reconciler *reconciliation.Reconciler) models.ReadinessReport {
	now := time.Now().UTC()
	var blockingReasons []string

	// 1. Process Liveness
	processStatus := "online"

	// 2. Journal Readiness
	journalReady := engine.IsJournalReady()
	if !journalReady {
		blockingReasons = append(blockingReasons, "journal_not_ready")
	}

	// 3. Broker Health & Connectivity
	activeBroker, _ := brokerReg.GetActive()
	activeBrokerName := "none"
	brokerConfigured := false
	brokerConnected := false
	brokerReady := false
	execMode := "SIMULATION"

	if activeBroker != nil {
		activeBrokerName = activeBroker.Name()
		health := activeBroker.GetHealth()
		brokerConfigured = health.Configured
		brokerConnected = health.Connected
		brokerReady = health.Ready
		execMode = string(health.Environment)

		if !brokerReady {
			blockingReasons = append(blockingReasons, fmt.Sprintf("broker_%s_not_ready", activeBrokerName))
		}
		if !brokerConnected {
			blockingReasons = append(blockingReasons, fmt.Sprintf("broker_%s_not_connected", activeBrokerName))
		}
	} else {
		blockingReasons = append(blockingReasons, "no_active_broker_configured")
	}

	// 4. Reconciliation Status & Freshness
	reconStatus, isFresh, lastRunAt, critCount, totCount, reconBroker := reconciler.GetSummary(now)
	reconSummary := models.ReconciliationSummary{
		Status:        reconStatus,
		LastRunAt:     lastRunAt,
		CriticalCount: critCount,
		TotalCount:    totCount,
		IsFresh:       isFresh,
		MaxAgeSeconds: int(reconciler.MaxAge.Seconds()),
		BrokerName:    reconBroker,
	}

	if reconStatus == "UNKNOWN" {
		blockingReasons = append(blockingReasons, "reconciliation_not_run")
	} else if reconStatus == "STALE" {
		blockingReasons = append(blockingReasons, "reconciliation_stale")
	} else if critCount > 0 || reconStatus == "MISMATCH" {
		blockingReasons = append(blockingReasons, fmt.Sprintf("reconciliation_critical_discrepancies_%d", critCount))
	}

	// 5. Freeze & Kill Switch State
	isFrozen, freezeReason, frozenAt, frozenBy, _ := engine.GetFreezeInfo()
	if isFrozen {
		if freezeReason == "" {
			freezeReason = "emergency manual freeze"
		}
		blockingReasons = append(blockingReasons, fmt.Sprintf("oms_frozen: %s", freezeReason))
	}

	// 6. Market Data Freshness
	allTicks := gateway.GetAllTicks()
	marketStatus := "UNAVAILABLE"
	var latestTickTime *time.Time
	if len(allTicks) > 0 {
		isDemo := false
		for _, tick := range allTicks {
			if tick.IsSimulated || tick.Source == "demo" {
				isDemo = true
			}
			if latestTickTime == nil || tick.Timestamp.After(*latestTickTime) {
				t := tick.Timestamp
				latestTickTime = &t
			}
		}
		if isDemo {
			marketStatus = "DEMO"
		} else {
			marketStatus = "LIVE"
		}
	}
	marketSummary := models.MarketDataSummary{
		Status:    marketStatus,
		UpdatedAt: latestTickTime,
		TickCount: len(allTicks),
	}

	// 7. Trading Readiness
	tradingReadiness := models.TradingReady
	tradingReady := false

	if isFrozen {
		tradingReadiness = models.TradingFrozen
	} else if len(blockingReasons) > 0 {
		tradingReadiness = models.TradingNotReady
	} else {
		tradingReadiness = models.TradingReady
		tradingReady = true
	}

	return models.ReadinessReport{
		Process:          processStatus,
		TradingReady:     tradingReady,
		TradingReadiness: tradingReadiness,
		ExecutionMode:    execMode,
		ActiveBroker:     activeBrokerName,
		BrokerConfigured: brokerConfigured,
		BrokerConnected:  brokerConnected,
		BrokerReady:      brokerReady,
		JournalReady:     journalReady,
		Reconciliation:   reconSummary,
		IsFrozen:         isFrozen,
		FreezeReason:     freezeReason,
		FrozenAt:         frozenAt,
		FrozenBy:         frozenBy,
		MarketData:       marketSummary,
		BlockingReasons:  blockingReasons,
		Timestamp:        now,
	}
}

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

	reconcilerMaxAge := 300 * time.Second
	if maxAgeStr := os.Getenv("RECONCILIATION_MAX_AGE_SECONDS"); maxAgeStr != "" {
		if sec, err := strconv.Atoi(maxAgeStr); err == nil && sec > 0 {
			reconcilerMaxAge = time.Duration(sec) * time.Second
		}
	}
	reconciler := reconciliation.NewReconciler(0.001, 1.0, 5*time.Minute)
	reconciler.SetMaxAge(reconcilerMaxAge)

	journalPath := os.Getenv("OMS_JOURNAL_PATH")
	if journalPath == "" {
		journalPath = "data/oms_journal.jsonl"
	}
	journal, err := oms.NewJournal(journalPath)
	if err != nil {
		engine.SetJournalReady(false)
		engine.FreezeWithReason(fmt.Sprintf("journal initialization failed: %v", err), "startup_journal", "")
		log.Printf("[JOURNAL ERROR] Could not initialize journal %s: %v. OMS state: FROZEN", journalPath, err)
	} else {
		engine.SetJournal(journal)
		replayed, err := journal.Replay(engine)
		if err != nil {
			engine.FreezeWithReason(fmt.Sprintf("journal replay failed: %v", err), "startup_journal", "")
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
			_ = brokerReg.SetActive("paper-simulation")
			log.Printf("[BROKER POSTURE] Active broker set to default Paper Simulation Adapter")
		} else {
			_ = brokerReg.SetActive("alpaca-paper")
			log.Printf("[BROKER POSTURE] Active broker set to Alpaca Paper Adapter")
		}
	case "webull":
		if webullKey == "" || webullSecret == "" {
			log.Printf("[BROKER WARNING] EXECUTION_BROKER=webull requested but credentials missing; operating in safe paper simulation fallback")
			_ = brokerReg.SetActive("paper-simulation")
			log.Printf("[BROKER POSTURE] Active broker set to default Paper Simulation Adapter")
		} else {
			_ = brokerReg.SetActive("webull-main")
			log.Printf("[BROKER POSTURE] Active broker set to Webull Main Adapter")
		}
	default:
		_ = brokerReg.SetActive("paper-simulation")
		log.Printf("[BROKER POSTURE] Active broker set to default Paper Simulation Adapter")
	}

	// Market Ticks Startup: Default to UNAVAILABLE unless DEMO_MARKET_DATA=true is explicitly set
	if strings.EqualFold(os.Getenv("DEMO_MARKET_DATA"), "true") {
		gateway.PublishTick(models.MarketTick{
			Symbol:      "SPY",
			Price:       512.45,
			Volume:      4500000,
			Timestamp:   time.Now().UTC(),
			Source:      "demo",
			IsSimulated: true,
		})
		gateway.PublishTick(models.MarketTick{
			Symbol:      "NVDA",
			Price:       128.50,
			Volume:      12000000,
			Timestamp:   time.Now().UTC(),
			Source:      "demo",
			IsSimulated: true,
		})
		gateway.PublishTick(models.MarketTick{
			Symbol:      "QQQ",
			Price:       445.20,
			Volume:      3200000,
			Timestamp:   time.Now().UTC(),
			Source:      "demo",
			IsSimulated: true,
		})
		log.Printf("[MARKET GATEWAY] DEMO_MARKET_DATA=true; published simulated demonstration ticks")
	} else {
		log.Printf("[MARKET GATEWAY] Production/Paper posture: No market ticks seeded (status: UNAVAILABLE)")
	}

	// Startup Reconciliation Gate: Fail closed if snapshot unavailable or critical discrepancy exists
	activeB, _ := brokerReg.GetActive()
	if activeB != nil {
		snap, err := activeB.GetBrokerSnapshot()
		if err != nil {
			engine.FreezeWithReason(fmt.Sprintf("startup broker snapshot unavailable: %v", err), "startup_gate", "")
			log.Printf("[STARTUP GATE] Failed to obtain broker snapshot: %v. OMS state: FROZEN", err)
		} else {
			localSnap := engine.ConstructLocalSnapshot()
			diff := reconciler.Reconcile(localSnap, *snap)
			reconciler.RecordRun(activeB.Name(), diff)
			if diff.HasCritical {
				engine.FreezeWithReason(fmt.Sprintf("startup critical reconciliation discrepancy (%d critical)", diff.TotalCount), "startup_gate", "")
				log.Printf("[STARTUP GATE] Critical reconciliation discrepancy detected. OMS state: FROZEN (%d discrepancies)", diff.TotalCount)
			} else {
				log.Printf("[STARTUP GATE] Startup reconciliation clean. OMS state: READY")
			}
		}
	} else {
		engine.FreezeWithReason("no active broker registered", "startup_gate", "")
		log.Printf("[STARTUP GATE] No active broker registered. OMS state: FROZEN")
	}

	mux := setupRouter(engine, brokerReg, gateway, reconciler)

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

func setupRouter(engine *oms.Engine, brokerReg *broker.Registry, gateway *market.Gateway, reconciler *reconciliation.Reconciler) *http.ServeMux {
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

	// 1. Health & Liveness / Readiness Probes
	mux.HandleFunc("GET /health/live", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":    "online",
			"process":   "aq-engine-go",
			"timestamp": time.Now().UTC(),
		})
	})

	mux.HandleFunc("GET /health/ready", func(w http.ResponseWriter, r *http.Request) {
		report := computeReadiness(engine, brokerReg, gateway, reconciler)
		w.Header().Set("Content-Type", "application/json")
		if !report.TradingReady {
			w.WriteHeader(http.StatusServiceUnavailable)
		}
		json.NewEncoder(w).Encode(report)
	})

	mux.HandleFunc("GET /api/v1/readiness", func(w http.ResponseWriter, r *http.Request) {
		report := computeReadiness(engine, brokerReg, gateway, reconciler)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(report)
	})

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		report := computeReadiness(engine, brokerReg, gateway, reconciler)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":            report.Process,
			"trading_ready":     report.TradingReady,
			"trading_readiness": report.TradingReadiness,
			"engine":            "aq-engine-go",
			"version":           "1.3.0-enterprise",
			"uptime_seconds":    time.Since(startTime).Seconds(),
			"active_broker":     report.ActiveBroker,
			"execution_mode":    report.ExecutionMode,
			"is_frozen":         report.IsFrozen,
			"freeze_reason":     report.FreezeReason,
			"reconciliation":    report.Reconciliation,
			"blocking_reasons":  report.BlockingReasons,
			"brokers":           brokerReg.List(),
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
		var req struct {
			Reason      string `json:"reason"`
			RequestedBy string `json:"requested_by"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if req.Reason == "" {
			req.Reason = "Emergency Kill Switch ENGAGED by operator"
		}
		if req.RequestedBy == "" {
			req.RequestedBy = "operator"
		}

		engine.FreezeWithReason(req.Reason, req.RequestedBy, "")
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":    "frozen",
			"is_frozen": true,
			"reason":    req.Reason,
			"message":   "Emergency Kill Switch ENGAGED: All new order submissions are BLOCKED",
			"timestamp": time.Now().UTC(),
		})
	})

	// 8. Safe Gated Resume / Unfreeze Execution
	mux.HandleFunc("POST /api/v1/risk/unfreeze", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Reason              string `json:"reason"`
			RequestedBy         string `json:"requested_by"`
			ReconciliationRunID string `json:"reconciliation_run_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)

		now := time.Now().UTC()
		var blockingReasons []string

		if strings.TrimSpace(req.Reason) == "" {
			blockingReasons = append(blockingReasons, "unfreeze_reason_required")
		}

		if !engine.IsJournalReady() {
			blockingReasons = append(blockingReasons, "journal_not_ready")
		}

		activeB, err := brokerReg.GetActive()
		if err != nil || activeB == nil {
			blockingReasons = append(blockingReasons, "no_active_broker_configured")
		}

		reconStatus, isFresh, _, critCount, _, reconBroker := reconciler.GetSummary(now)
		if reconStatus == "UNKNOWN" {
			blockingReasons = append(blockingReasons, "reconciliation_never_run")
		} else if !isFresh {
			blockingReasons = append(blockingReasons, "reconciliation_evidence_stale")
		} else if reconStatus == "MISMATCH" || critCount > 0 {
			if critCount == 0 {
				critCount = 1
			}
			blockingReasons = append(blockingReasons, fmt.Sprintf("critical_discrepancies_present_%d", critCount))
		} else if activeB != nil && reconBroker != activeB.Name() {
			blockingReasons = append(blockingReasons, fmt.Sprintf("reconciliation_broker_mismatch_last_%s_active_%s", reconBroker, activeB.Name()))
		}

		if len(blockingReasons) > 0 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"resumed":          false,
				"is_frozen":        true,
				"blocking_reasons": blockingReasons,
				"message":          "Execution resume BLOCKED: Safety preconditions not satisfied",
			})
			return
		}

		by := req.RequestedBy
		if by == "" {
			by = "local-operator"
		}
		engine.UnfreezeWithReason(req.Reason, by, req.ReconciliationRunID)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"resumed":   true,
			"is_frozen": false,
			"reason":    req.Reason,
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
		reconciler.RecordRun(activeB.Name(), diff)
		metrics.DefaultRegistry.AddReconciliationDiscrepancies(uint64(diff.TotalCount))
		if diff.HasCritical {
			engine.FreezeWithReason(fmt.Sprintf("critical reconciliation discrepancy (%d critical)", diff.TotalCount), "reconciliation_engine", "")
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
			http.Error(w, "invalid request payload", http.StatusBadRequest)
			return
		}
		currentActive, _ := brokerReg.GetActive()
		currentName := ""
		if currentActive != nil {
			currentName = currentActive.Name()
		}

		if err := brokerReg.SetActive(req.Name); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		if currentName != req.Name {
			reconciler.Invalidate()
			engine.FreezeWithReason(fmt.Sprintf("active broker changed from %s to %s; reconciliation required", currentName, req.Name), "broker_manager", "")
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "selected",
			"active": req.Name,
		})
	})

	return mux
}
