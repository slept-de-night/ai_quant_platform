package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"aq-engine-go/broker"
	"aq-engine-go/market"
	"aq-engine-go/models"
	"aq-engine-go/oms"
)

func setupTestServer() (*http.ServeMux, *oms.Engine, *broker.Registry) {
	riskCfg := models.DefaultRiskConfig()
	engine := oms.NewEngine(100000.0, riskCfg)
	gateway := market.NewGateway()
	brokerReg := broker.NewRegistry()
	paperAdapter := broker.NewPaperAdapter("paper-sim", 100000.0)
	brokerReg.Register(paperAdapter)

	mux := setupRouter(engine, brokerReg, gateway)
	return mux, engine, brokerReg
}

func TestHTTPRiskCheckPure(t *testing.T) {
	mux, engine, _ := setupTestServer()

	order := models.OrderIntent{
		Symbol:         "NVDA",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 130.0,
		Notional:       1300.0,
		ClientOrderID:  "http-pure-risk-1",
		TraceID:        "trace-http-1",
	}

	body, _ := json.Marshal(order)
	req := httptest.NewRequest("POST", "/api/v1/risk/check", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Expected 200 OK, got %d", w.Code)
	}

	var decision models.RiskDecision
	if err := json.NewDecoder(w.Body).Decode(&decision); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}
	if !decision.Approved {
		t.Fatalf("Expected risk approved, got: %v", decision.Reasons)
	}

	// Verify pure: 0 orders in engine
	if len(engine.GetOrderHistory()) != 0 {
		t.Fatalf("Expected 0 orders in history, found %d", len(engine.GetOrderHistory()))
	}
	if engine.GetPortfolio("").OrdersToday != 0 {
		t.Fatalf("Expected OrdersToday=0, got %d", engine.GetPortfolio("").OrdersToday)
	}
}

func TestHTTPOderSubmitAndIdempotency(t *testing.T) {
	mux, engine, _ := setupTestServer()

	order := models.OrderIntent{
		Symbol:         "AAPL",
		Side:           models.SideBuy,
		Qty:            10,
		ReferencePrice: 200.0,
		Notional:       2000.0,
		ClientOrderID:  "http-submit-1",
		TraceID:        "trace-submit-1",
	}

	body, _ := json.Marshal(order)

	// 1. First Submit -> 200 OK
	req1 := httptest.NewRequest("POST", "/api/v1/orders/submit", bytes.NewReader(body))
	w1 := httptest.NewRecorder()
	mux.ServeHTTP(w1, req1)

	if w1.Code != http.StatusOK {
		t.Fatalf("First submit expected 200 OK, got %d: %s", w1.Code, w1.Body.String())
	}

	var res1 map[string]interface{}
	json.NewDecoder(w1.Body).Decode(&res1)
	if res1["submitted"] != true {
		t.Fatalf("Expected submitted=true, got %v", res1)
	}

	// Verify 1 order in history
	if len(engine.GetOrderHistory()) != 1 {
		t.Fatalf("Expected 1 order in history, got %d", len(engine.GetOrderHistory()))
	}

	// 2. Duplicate Submit with same client_order_id -> Rejected, submitted=false
	req2 := httptest.NewRequest("POST", "/api/v1/orders/submit", bytes.NewReader(body))
	w2 := httptest.NewRecorder()
	mux.ServeHTTP(w2, req2)

	var res2 map[string]interface{}
	json.NewDecoder(w2.Body).Decode(&res2)
	if res2["submitted"] == true {
		t.Fatalf("Duplicate submit should not be submitted=true")
	}

	// Order count remains 1
	if len(engine.GetOrderHistory()) != 1 {
		t.Fatalf("Duplicate submit corrupted order count: %d", len(engine.GetOrderHistory()))
	}
}

func TestHTTPKillSwitchAndReadOnlyAccess(t *testing.T) {
	mux, engine, _ := setupTestServer()

	// 1. Engage kill switch
	killReq := httptest.NewRequest("POST", "/api/v1/risk/kill", nil)
	killW := httptest.NewRecorder()
	mux.ServeHTTP(killW, killReq)

	if killW.Code != http.StatusOK {
		t.Fatalf("Expected 200 from kill endpoint, got %d", killW.Code)
	}
	if !engine.IsFrozen() {
		t.Fatalf("Expected engine to be frozen")
	}

	// 2. Submit order should fail
	order := models.OrderIntent{
		Symbol:         "MSFT",
		Side:           models.SideBuy,
		Qty:            5,
		ReferencePrice: 400.0,
		Notional:       2000.0,
		ClientOrderID:  "frozen-order-1",
	}
	submitBody, _ := json.Marshal(order)
	subReq := httptest.NewRequest("POST", "/api/v1/orders/submit", bytes.NewReader(submitBody))
	subW := httptest.NewRecorder()
	mux.ServeHTTP(subW, subReq)

	var subRes map[string]interface{}
	json.NewDecoder(subW.Body).Decode(&subRes)
	if subRes["submitted"] == true {
		t.Fatalf("Expected submission to be rejected while frozen")
	}

	// 3. Read portfolio while frozen
	portReq := httptest.NewRequest("GET", "/api/v1/portfolio?symbol=MSFT", nil)
	portW := httptest.NewRecorder()
	mux.ServeHTTP(portW, portReq)

	if portW.Code != http.StatusOK {
		t.Fatalf("Portfolio query failed while frozen: %d", portW.Code)
	}

	// 4. Read orders history while frozen
	histReq := httptest.NewRequest("GET", "/api/v1/orders/history", nil)
	histW := httptest.NewRecorder()
	mux.ServeHTTP(histW, histReq)

	if histW.Code != http.StatusOK {
		t.Fatalf("Orders history query failed while frozen: %d", histW.Code)
	}
}

func TestHTTPBrokersHealthAndSwitch(t *testing.T) {
	mux, _, brokerReg := setupTestServer()

	// Register extra broker
	alpaca := broker.NewAlpacaAdapter("alpaca-paper", "", "", true)
	brokerReg.Register(alpaca)

	// 1. GET /api/v1/brokers/health
	healthReq := httptest.NewRequest("GET", "/api/v1/brokers/health", nil)
	healthW := httptest.NewRecorder()
	mux.ServeHTTP(healthW, healthReq)

	if healthW.Code != http.StatusOK {
		t.Fatalf("Expected 200 from /api/v1/brokers/health, got %d", healthW.Code)
	}

	var healthRes broker.BrokerHealthResponse
	if err := json.NewDecoder(healthW.Body).Decode(&healthRes); err != nil {
		t.Fatalf("Failed to decode health response: %v", err)
	}
	if healthRes.ActiveBroker != "paper-sim" {
		t.Fatalf("Expected active broker 'paper-sim', got '%s'", healthRes.ActiveBroker)
	}
	if !healthRes.Ready {
		t.Fatalf("Expected Ready=true in health response")
	}
	if len(healthRes.AllRegisteredBrokers) != 2 {
		t.Fatalf("Expected 2 registered brokers, got %d", len(healthRes.AllRegisteredBrokers))
	}

	// 2. POST /api/v1/brokers/select to switch to alpaca-paper
	switchBody, _ := json.Marshal(map[string]string{"name": "alpaca-paper"})
	switchReq := httptest.NewRequest("POST", "/api/v1/brokers/select", bytes.NewReader(switchBody))
	switchW := httptest.NewRecorder()
	mux.ServeHTTP(switchW, switchReq)

	if switchW.Code != http.StatusOK {
		t.Fatalf("Expected 200 from /api/v1/brokers/select, got %d", switchW.Code)
	}

	active, err := brokerReg.GetActive()
	if err != nil || active.Name() != "alpaca-paper" {
		t.Fatalf("Expected active broker to switch to alpaca-paper, got %v", active)
	}
}

func TestHTTPMetricsEndpoints(t *testing.T) {
	mux, _, _ := setupTestServer()

	// 1. GET /metrics (Prometheus text)
	promReq := httptest.NewRequest("GET", "/metrics", nil)
	promW := httptest.NewRecorder()
	mux.ServeHTTP(promW, promReq)

	if promW.Code != http.StatusOK {
		t.Fatalf("Expected 200 from /metrics, got %d", promW.Code)
	}
	promBody := promW.Body.String()
	if !strings.Contains(promBody, "aq_engine_uptime_seconds") {
		t.Fatalf("Expected Prometheus output to contain aq_engine_uptime_seconds: %s", promBody)
	}

	// 2. GET /api/v1/metrics (JSON)
	jsonReq := httptest.NewRequest("GET", "/api/v1/metrics", nil)
	jsonW := httptest.NewRecorder()
	mux.ServeHTTP(jsonW, jsonReq)

	if jsonW.Code != http.StatusOK {
		t.Fatalf("Expected 200 from /api/v1/metrics, got %d", jsonW.Code)
	}
	var snap map[string]interface{}
	if err := json.NewDecoder(jsonW.Body).Decode(&snap); err != nil {
		t.Fatalf("Failed to decode JSON metrics: %v", err)
	}
	if _, ok := snap["uptime_seconds"]; !ok {
		t.Fatalf("Expected uptime_seconds in JSON snapshot")
	}
}

