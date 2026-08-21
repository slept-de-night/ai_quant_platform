package webull

import (
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"
)

// TestSigner_OfficialWorkedVector verifies the exact official Webull HMAC-SHA1
// signature output using the published worked example, matching the official
// deterministic test vector exactly (acceptance: official inputs -> official output).
func TestSigner_OfficialWorkedVector(t *testing.T) {
	creds := Credentials{
		AppKey:      "776da210ab4a452795d74e726ebd74b6",
		AppSecret:   "0f50a2e853334a9aae1a783bee120c1f",
		Environment: EnvSandbox,
	}

	signer, err := NewSigner(creds)
	if err != nil {
		t.Fatalf("NewSigner failed: %v", err)
	}

	path := "/trade/place_order"
	query := url.Values{
		"a1": []string{"webull"},
		"a2": []string{"123"},
		"a3": []string{"xxx"},
		"q1": []string{"yyy"},
	}
	body := []byte(`{"k1":123,"k2":"this is the api request body","k3":true,"k4":{"foo":[1,2]}}`)
	timestamp := "2022-01-04T03:55:31Z"
	nonce := "48ef5afed43d4d91ae514aaeafbc29ba"

	sig, _, err := signer.Sign("api.webull.com", path, query, body, timestamp, nonce)
	if err != nil {
		t.Fatalf("Sign failed: %v", err)
	}

	// Official worked-example result. If this mismatches, the signer is not
	// producing the official signature and must be corrected before D2.
	if sig != "kvlS6opdZDhEBo5jq40nHYXaLvM=" {
		t.Fatalf("Official signature vector mismatch!\nExpected: kvlS6opdZDhEBo5jq40nHYXaLvM=\nGot:      %s", sig)
	}
}

// TestSigner_CanonicalConsistency verifies the canonical signing string is
// internally consistent with the returned signature: the signature must equal
// Base64(HMAC-SHA1(appSecret + "&", percentEncodeAll(canonical))).
func TestSigner_CanonicalConsistency(t *testing.T) {
	creds := Credentials{
		AppKey:      "mem-a-key",
		AppSecret:   "mem-app-secret-0123456789abcdef",
		Environment: EnvSandbox,
	}

	signer, err := NewSigner(creds)
	if err != nil {
		t.Fatalf("NewSigner failed: %v", err)
	}

	query := url.Values{
		"a1": []string{"webull"},
		"a2": []string{"123"},
		"a3": []string{"xxx"},
		"q1": []string{"yyy"},
	}
	body := []byte(`{"k1":123,"k2":"this is the api request body","k3":true,"k4":{"foo":[1,2]}}`)

	sig, canonical, err := signer.Sign("api.webull.com", "/trade/place_order", query, body,
		"2022-01-04T03:55:31Z", "48ef5afed43d4d91ae514aaeafbc29ba")
	if err != nil {
		t.Fatalf("Sign failed: %v", err)
	}
	if canonical == "" || sig == "" {
		t.Fatalf("Expected non-empty canonical and signature")
	}

	expected := percentEncodeAll(canonical)
	key := creds.AppSecret + "&"
	mac := hmac.New(sha1.New, []byte(key))
	mac.Write([]byte(expected))
	recomputed := base64.StdEncoding.EncodeToString(mac.Sum(nil))

	if sig != recomputed {
		t.Fatalf("Signature not consistent with canonical!\nExpected: %s\nGot:      %s", recomputed, sig)
	}
}

// TestCredentials_Validation verifies credential completeness and environment guards.
func TestCredentials_Validation(t *testing.T) {
	c1 := Credentials{AppKey: "", AppSecret: "secret", Environment: EnvSandbox}
	if err := c1.Validate(); err == nil {
		t.Fatalf("Expected error for missing AppKey")
	}

	c2 := Credentials{AppKey: "key", AppSecret: "", Environment: EnvSandbox}
	if err := c2.Validate(); err == nil {
		t.Fatalf("Expected error for missing AppSecret")
	}

	c3 := Credentials{AppKey: "key", AppSecret: "secret", Environment: "UNKNOWN"}
	if err := c3.Validate(); err == nil {
		t.Fatalf("Expected error for invalid environment")
	}

	c4 := Credentials{AppKey: "key", AppSecret: "secret", Environment: EnvSandbox}
	if err := c4.Validate(); err != nil {
		t.Fatalf("Expected valid sandbox credentials, got: %v", err)
	}

	c5 := Credentials{AppKey: "key", AppSecret: "secret", Environment: EnvLive}
	if err := c5.Validate(); err != nil {
		t.Fatalf("Expected valid live credentials, got: %v", err)
	}
}

// TestSigner_ApplyHeaders verifies official header decoration and that the app
// secret is never transmitted as a request header.
func TestSigner_ApplyHeaders(t *testing.T) {
	creds := Credentials{
		AppKey:      "my-app-key",
		AppSecret:   "my-super-secret-key-32charslong!",
		AccountID:   "acc-9988",
		AccessToken: "wb-access-token-abc",
		Environment: EnvSandbox,
	}

	signer, err := NewSigner(creds)
	if err != nil {
		t.Fatalf("NewSigner failed: %v", err)
	}

	req, err := http.NewRequest("GET", "https://api.sandbox.webull.com/v2/account/positions?symbol=NVDA", nil)
	if err != nil {
		t.Fatalf("NewRequest failed: %v", err)
	}

	now := time.Date(2026, 8, 21, 12, 30, 0, 0, time.UTC)
	err = signer.ApplyHeaders(req, nil, now)
	if err != nil {
		t.Fatalf("ApplyHeaders failed: %v", err)
	}

	if req.Header.Get("x-app-key") != "my-app-key" {
		t.Fatalf("Expected x-app-key 'my-app-key', got '%s'", req.Header.Get("x-app-key"))
	}
	if req.Header.Get("x-timestamp") != "2026-08-21T12:30:00Z" {
		t.Fatalf("Expected x-timestamp '2026-08-21T12:30:00Z', got '%s'", req.Header.Get("x-timestamp"))
	}
	if req.Header.Get("x-signature-algorithm") != "HMAC-SHA1" {
		t.Fatalf("Expected x-signature-algorithm HMAC-SHA1, got '%s'", req.Header.Get("x-signature-algorithm"))
	}
	if req.Header.Get("x-signature-version") != "1.0" {
		t.Fatalf("Expected x-signature-version 1.0, got '%s'", req.Header.Get("x-signature-version"))
	}
	if req.Header.Get("x-version") != "v2" {
		t.Fatalf("Expected x-version v2, got '%s'", req.Header.Get("x-version"))
	}
	if req.Header.Get("x-signature-nonce") == "" {
		t.Fatalf("Expected non-empty x-signature-nonce header")
	}
	if req.Header.Get("x-signature") == "" {
		t.Fatalf("Expected non-empty x-signature header")
	}
	if req.Header.Get("x-access-token") != "wb-access-token-abc" {
		t.Fatalf("Expected x-access-token 'wb-access-token-abc', got '%s'", req.Header.Get("x-access-token"))
	}

	// The app secret must never be present as a request header.
	for _, name := range strings.Split("x-app-key x-timestamp x-signature x-signature-algorithm x-signature-version x-signature-nonce x-version x-access-token", " ") {
		h := req.Header.Get(name)
		if h != "" && strings.Contains(h, creds.AppSecret) {
			t.Fatalf("App secret leaked via header %s", name)
		}
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
	if len(n1) != 32 {
		t.Fatalf("Expected 32 hex chars for 16 bytes, got %d", len(n1))
	}
}