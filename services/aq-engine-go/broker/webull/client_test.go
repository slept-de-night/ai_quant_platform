package webull

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// TestClient_OfficialBaseURLs verifies sandbox and live environments resolve to
// the current official Webull OpenAPI hosts.
func TestClient_OfficialBaseURLs(t *testing.T) {
	sandbox := Credentials{AppKey: "k", AppSecret: "s", Environment: EnvSandbox}
	live := Credentials{AppKey: "k", AppSecret: "s", Environment: EnvLive}

	sc, err := NewClient(sandbox)
	if err != nil {
		t.Fatalf("NewClient(sandbox) failed: %v", err)
	}
	if sc.baseURL != "https://api.sandbox.webull.com" {
		t.Fatalf("Sandbox base URL mismatch, got '%s'", sc.baseURL)
	}
	if sc.baseURL == SandboxBaseURL && SandboxBaseURL != "https://api.sandbox.webull.com" {
		t.Fatalf("SandboxBaseURL constant is not the official host")
	}

	lc, err := NewClient(live)
	if err != nil {
		t.Fatalf("NewClient(live) failed: %v", err)
	}
	if lc.baseURL != "https://api.webull.com" {
		t.Fatalf("Live base URL mismatch, got '%s'", lc.baseURL)
	}
	if LiveBaseURL != "https://api.webull.com" {
		t.Fatalf("LiveBaseURL constant is not the official host")
	}
}

// TestClient_429RetryBackoffAndRecovery verifies that HTTP 429 triggers exponential backoff and recovers upon subsequent 200 OK.
func TestClient_429RetryBackoffAndRecovery(t *testing.T) {
	var attempts int32

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		att := atomic.AddInt32(&attempts, 1)
		if att < 3 {
			w.WriteHeader(http.StatusTooManyRequests)
			w.Write([]byte(`{"code":"RATE_LIMIT_EXCEEDED"}`))
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"success":true,"message":"ok"}`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key_12345",
		AppSecret:   "wb_test_secret_67890",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds,
		WithBaseURL(server.URL),
		WithMaxRetries(3),
		WithBackoff(5*time.Millisecond, 20*time.Millisecond),
	)
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	code, body, err := client.Execute(context.Background(), "GET", "/api/v1/test", nil, nil)
	if err != nil {
		t.Fatalf("Execute failed after retries: %v", err)
	}

	if code != http.StatusOK {
		t.Fatalf("Expected status 200, got %d", code)
	}
	if !strings.Contains(string(body), `"success":true`) {
		t.Fatalf("Expected success body, got %s", string(body))
	}
	if atomic.LoadInt32(&attempts) != 3 {
		t.Fatalf("Expected 3 attempts, got %d", atomic.LoadInt32(&attempts))
	}
}

// TestClient_5xxMaxRetriesFail verifies that persistent HTTP 5xx fails closed after exceeding maximum retry attempts.
func TestClient_5xxMaxRetriesFail(t *testing.T) {
	var attempts int32

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&attempts, 1)
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"error":"Service temporarily unavailable"}`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key_12345",
		AppSecret:   "wb_test_secret_67890",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds,
		WithBaseURL(server.URL),
		WithMaxRetries(2),
		WithBackoff(5*time.Millisecond, 10*time.Millisecond),
	)
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	_, _, err = client.Execute(context.Background(), "POST", "/api/v1/order", nil, []byte(`{}`))
	if err == nil {
		t.Fatalf("Expected error for 503 service unavailable")
	}

	if !IsServerError(err) {
		t.Fatalf("Expected IsServerError to return true for 503, got error: %v", err)
	}

	// 1 initial attempt + 2 retries = 3 total attempts
	if atomic.LoadInt32(&attempts) != 3 {
		t.Fatalf("Expected 3 attempts (1 + 2 retries), got %d", atomic.LoadInt32(&attempts))
	}
}

// TestClient_401Unauthorized_NoRetry verifies that authentication failures fail immediately without wasting retries.
func TestClient_401Unauthorized_NoRetry(t *testing.T) {
	var attempts int32

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&attempts, 1)
		w.WriteHeader(http.StatusUnauthorized)
		w.Write([]byte(`{"error":"Invalid signature"}`))
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key_12345",
		AppSecret:   "wb_test_secret_67890",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds,
		WithBaseURL(server.URL),
		WithMaxRetries(3),
	)
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	code, _, err := client.Execute(context.Background(), "GET", "/api/v1/account", nil, nil)
	if err == nil {
		t.Fatalf("Expected error for 401 unauthorized")
	}

	if code != http.StatusUnauthorized {
		t.Fatalf("Expected HTTP 401, got %d", code)
	}

	if !IsAuthError(err) {
		t.Fatalf("Expected IsAuthError to return true, got: %v", err)
	}

	// Auth errors must NOT retry
	if atomic.LoadInt32(&attempts) != 1 {
		t.Fatalf("Expected exactly 1 attempt for 401 without retry, got %d", atomic.LoadInt32(&attempts))
	}
}

// TestClient_RedactLogMessage verifies secret redaction in logging output.
func TestClient_RedactLogMessage(t *testing.T) {
	creds := Credentials{
		AppKey:      "wb_production_app_key_9999",
		AppSecret:   "ultra_sensitive_secret_value_xyz!",
		Environment: EnvLive,
	}

	client, err := NewClient(creds)
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	rawLog := "Failed request with app_key wb_production_app_key_9999 and secret ultra_sensitive_secret_value_xyz! to server"
	redacted := client.RedactLogMessage(rawLog)

	if strings.Contains(redacted, creds.AppSecret) {
		t.Fatalf("AppSecret was leaked in log: %s", redacted)
	}
	if strings.Contains(redacted, creds.AppKey) {
		t.Fatalf("AppKey was leaked in log: %s", redacted)
	}
	if !strings.Contains(redacted, "[REDACTED_APP_SECRET]") {
		t.Fatalf("Expected [REDACTED_APP_SECRET] placeholder: %s", redacted)
	}
	if !strings.Contains(redacted, "[REDACTED_APP_KEY]") {
		t.Fatalf("Expected [REDACTED_APP_KEY] placeholder: %s", redacted)
	}
}

// TestClient_AmbiguousTimeoutClassification verifies transport timeout error predicate.
func TestClient_AmbiguousTimeoutClassification(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(100 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	creds := Credentials{
		AppKey:      "wb_test_key_12345",
		AppSecret:   "wb_test_secret_67890",
		Environment: EnvSandbox,
	}

	client, err := NewClient(creds,
		WithBaseURL(server.URL),
		WithMaxRetries(0),
	)
	if err != nil {
		t.Fatalf("NewClient failed: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()

	_, _, err = client.Execute(ctx, "POST", "/api/v1/orders", nil, []byte(`{}`))
	if err == nil {
		t.Fatalf("Expected timeout error")
	}

	if !IsAmbiguousTransportError(err) {
		t.Fatalf("Expected timeout to be classified as ambiguous transport error, got: %v", err)
	}
}
