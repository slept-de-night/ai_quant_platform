package auth

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestAuthMiddlewareProtectedEndpoints(t *testing.T) {
	configuredSecret := "sec-inst-token-xyz"
	mw := Middleware(configuredSecret, true)

	dummyHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("authorized"))
	})

	protectedHandler := mw(dummyHandler)

	// 1. Missing Token -> 401
	req1 := httptest.NewRequest("POST", "/api/v1/orders/submit", nil)
	w1 := httptest.NewRecorder()
	protectedHandler.ServeHTTP(w1, req1)
	if w1.Code != http.StatusUnauthorized {
		t.Fatalf("Expected 401 Unauthorized for missing token, got %d", w1.Code)
	}

	// 2. Invalid Token -> 401
	req2 := httptest.NewRequest("POST", "/api/v1/orders/submit", nil)
	req2.Header.Set("Authorization", "Bearer wrong-token")
	w2 := httptest.NewRecorder()
	protectedHandler.ServeHTTP(w2, req2)
	if w2.Code != http.StatusUnauthorized {
		t.Fatalf("Expected 401 Unauthorized for invalid token, got %d", w2.Code)
	}

	// 3. Valid Bearer Token -> 200
	req3 := httptest.NewRequest("POST", "/api/v1/orders/submit", nil)
	req3.Header.Set("Authorization", "Bearer "+configuredSecret)
	w3 := httptest.NewRecorder()
	protectedHandler.ServeHTTP(w3, req3)
	if w3.Code != http.StatusOK {
		t.Fatalf("Expected 200 OK for valid Bearer token, got %d", w3.Code)
	}

	// 4. Valid X-API-Key Header -> 200
	req4 := httptest.NewRequest("POST", "/api/v1/orders/submit", nil)
	req4.Header.Set("X-API-Key", configuredSecret)
	w4 := httptest.NewRecorder()
	protectedHandler.ServeHTTP(w4, req4)
	if w4.Code != http.StatusOK {
		t.Fatalf("Expected 200 OK for valid X-API-Key header, got %d", w4.Code)
	}

	// 5. Exemption for /health and /metrics without token
	req5 := httptest.NewRequest("GET", "/health", nil)
	w5 := httptest.NewRecorder()
	protectedHandler.ServeHTTP(w5, req5)
	if w5.Code != http.StatusOK {
		t.Fatalf("Expected 200 OK for /health exemption, got %d", w5.Code)
	}

	req6 := httptest.NewRequest("GET", "/metrics", nil)
	w6 := httptest.NewRecorder()
	protectedHandler.ServeHTTP(w6, req6)
	if w6.Code != http.StatusOK {
		t.Fatalf("Expected 200 OK for /metrics exemption, got %d", w6.Code)
	}
}

func TestSecretRedaction(t *testing.T) {
	secretKey := "AKIAIOSFODNN7EXAMPLE"
	rawMsg := "Failed to authenticate with key AKIAIOSFODNN7EXAMPLE against broker"
	redacted := RedactSecret(rawMsg, secretKey)
	if strings.Contains(redacted, secretKey) {
		t.Fatalf("Secret leaked in redacted output: %s", redacted)
	}
	if !strings.Contains(redacted, "[REDACTED]") {
		t.Fatalf("Expected [REDACTED] in message: %s", redacted)
	}
}

func TestValidateEnvironmentCredentials_LiveModeRequiresStrongSecret(t *testing.T) {
	// 1. Missing secret in live mode -> error
	err := ValidateEnvironmentCredentials("live", "", false)
	if err == nil {
		t.Fatalf("Expected error for missing AUTH_TOKEN in live mode")
	}

	// 2. Short secret in live mode -> error
	err = ValidateEnvironmentCredentials("live", "short-secret", false)
	if err == nil {
		t.Fatalf("Expected error for short AUTH_TOKEN in live mode")
	}

	// 3. Insecure default secret in live mode -> error
	err = ValidateEnvironmentCredentials("live", "password12345678", false)
	if err == nil {
		t.Fatalf("Expected error for default password AUTH_TOKEN in live mode")
	}

	// 4. Strong secret in live mode -> success
	err = ValidateEnvironmentCredentials("live", "high-entropy-secure-token-998877", false)
	if err != nil {
		t.Fatalf("Expected success for strong secret in live mode, got: %v", err)
	}
}

func TestValidateEnvironmentCredentials_SimulationMode(t *testing.T) {
	// Anonymous allowed in simulation mode when explicitly flagged
	err := ValidateEnvironmentCredentials("simulation", "", true)
	if err != nil {
		t.Fatalf("Expected success for anonymous local in simulation mode, got: %v", err)
	}

	// Anonymous rejected if allowAnonymousLocal is false
	err = ValidateEnvironmentCredentials("simulation", "", false)
	if err == nil {
		t.Fatalf("Expected error when anonymous local is disallowed")
	}
}

func TestGetListenAddress_DefaultsToLoopback(t *testing.T) {
	// 1. Empty host and port -> 127.0.0.1:8080 (never 0.0.0.0)
	addr1 := GetListenAddress("", "")
	if addr1 != "127.0.0.1:8080" {
		t.Fatalf("Expected default 127.0.0.1:8080, got %s", addr1)
	}

	// 2. Custom port -> 127.0.0.1:9090
	addr2 := GetListenAddress("", "9090")
	if addr2 != "127.0.0.1:9090" {
		t.Fatalf("Expected 127.0.0.1:9090, got %s", addr2)
	}

	// 3. Custom loopback host
	addr3 := GetListenAddress("127.0.0.2", "8085")
	if addr3 != "127.0.0.2:8085" {
		t.Fatalf("Expected 127.0.0.2:8085, got %s", addr3)
	}
}

