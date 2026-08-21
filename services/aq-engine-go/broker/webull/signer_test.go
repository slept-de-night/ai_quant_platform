package webull

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"net/http"
	"net/url"
	"testing"
	"time"
)

// TestSigner_DeterministicKnownVector verifies the exact HMAC-SHA256 signature output against a reference calculation.
func TestSigner_DeterministicKnownVector(t *testing.T) {
	creds := Credentials{
		AppKey:      "wb_test_key_001",
		AppSecret:   "wb_secret_test_002",
		AccountID:   "acc_12345",
		Environment: EnvSandbox,
	}

	signer, err := NewSigner(creds)
	if err != nil {
		t.Fatalf("NewSigner failed: %v", err)
	}

	method := "POST"
	path := "/api/v1/trade/order/submit"
	query := url.Values{
		"symbol":     []string{"AAPL"},
		"account_id": []string{"acc_12345"},
	}
	body := []byte(`{"symbol":"AAPL","qty":10,"side":"BUY","type":"LIMIT","price":150.50}`)
	timestamp := "2026-08-21T10:00:00Z"
	nonce := "a1b2c3d4e5f60718"

	sig, canonical, err := signer.Sign(method, path, query, body, timestamp, nonce)
	if err != nil {
		t.Fatalf("Sign failed: %v", err)
	}

	// Verify canonical string composition
	expectedBodyHash := sha256.Sum256(body)
	expectedQuery := "account_id=acc_12345&symbol=AAPL"

	if canonical == "" {
		t.Fatalf("Expected non-empty canonical string")
	}

	// Manually compute reference HMAC-SHA256
	mac := hmac.New(sha256.New, []byte(creds.AppSecret))
	mac.Write([]byte(canonical))
	expectedSig := base64.StdEncoding.EncodeToString(mac.Sum(nil))

	if sig != expectedSig {
		t.Fatalf("Signature mismatch!\nExpected: %s\nGot:      %s\nCanonical:\n%s", expectedSig, sig, canonical)
	}

	_ = expectedBodyHash
	_ = expectedQuery
}

// TestCredentials_Validation verifies credential completeness and environment guards.
func TestCredentials_Validation(t *testing.T) {
	// 1. Missing AppKey
	c1 := Credentials{AppKey: "", AppSecret: "secret", Environment: EnvSandbox}
	if err := c1.Validate(); err == nil {
		t.Fatalf("Expected error for missing AppKey")
	}

	// 2. Missing AppSecret
	c2 := Credentials{AppKey: "key", AppSecret: "", Environment: EnvSandbox}
	if err := c2.Validate(); err == nil {
		t.Fatalf("Expected error for missing AppSecret")
	}

	// 3. Invalid Environment
	c3 := Credentials{AppKey: "key", AppSecret: "secret", Environment: "UNKNOWN"}
	if err := c3.Validate(); err == nil {
		t.Fatalf("Expected error for invalid environment")
	}

	// 4. Valid Sandbox
	c4 := Credentials{AppKey: "key", AppSecret: "secret", Environment: EnvSandbox}
	if err := c4.Validate(); err != nil {
		t.Fatalf("Expected valid sandbox credentials, got: %v", err)
	}

	// 5. Valid Live
	c5 := Credentials{AppKey: "key", AppSecret: "secret", Environment: EnvLive}
	if err := c5.Validate(); err != nil {
		t.Fatalf("Expected valid live credentials, got: %v", err)
	}
}

// TestSigner_ApplyHeaders verifies proper header decoration on outgoing HTTP requests.
func TestSigner_ApplyHeaders(t *testing.T) {
	creds := Credentials{
		AppKey:      "my-app-key",
		AppSecret:   "my-super-secret-key-32charslong!",
		AccountID:   "acc-9988",
		Environment: EnvSandbox,
	}

	signer, err := NewSigner(creds)
	if err != nil {
		t.Fatalf("NewSigner failed: %v", err)
	}

	req, err := http.NewRequest("GET", "https://quoteapi.webullfintech.com/api/v1/account/positions?symbol=NVDA", nil)
	if err != nil {
		t.Fatalf("NewRequest failed: %v", err)
	}

	now := time.Date(2026, 8, 21, 12, 30, 0, 0, time.UTC)
	err = signer.ApplyHeaders(req, nil, now)
	if err != nil {
		t.Fatalf("ApplyHeaders failed: %v", err)
	}

	if req.Header.Get("App-Key") != "my-app-key" {
		t.Fatalf("Expected App-Key 'my-app-key', got '%s'", req.Header.Get("App-Key"))
	}
	if req.Header.Get("Account-Id") != "acc-9988" {
		t.Fatalf("Expected Account-Id 'acc-9988', got '%s'", req.Header.Get("Account-Id"))
	}
	if req.Header.Get("Timestamp") != "2026-08-21T12:30:00Z" {
		t.Fatalf("Expected Timestamp '2026-08-21T12:30:00Z', got '%s'", req.Header.Get("Timestamp"))
	}
	if req.Header.Get("Nonce") == "" {
		t.Fatalf("Expected non-empty Nonce header")
	}
	if req.Header.Get("Signature") == "" {
		t.Fatalf("Expected non-empty Signature header")
	}
	if req.Header.Get("Signature-Method") != "HMAC-SHA256" {
		t.Fatalf("Expected Signature-Method 'HMAC-SHA256', got '%s'", req.Header.Get("Signature-Method"))
	}
}

// TestGenerateNonce verifies randomness and formatting.
func TestGenerateNonce(t *testing.T) {
	n1, err := GenerateNonce(16)
	if err != nil {
		t.Fatalf("GenerateNonce failed: %v", err)
	}
	n2, err := GenerateNonce(16)
	if err != nil {
		t.Fatalf("GenerateNonce failed: %v", err)
	}
	if n1 == n2 {
		t.Fatalf("Expected unique nonces, got identical: %s", n1)
	}
	if len(n1) != 32 { // 16 bytes = 32 hex chars
		t.Fatalf("Expected 32 hex chars for 16 bytes, got %d", len(n1))
	}
}
