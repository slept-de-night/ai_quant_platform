package webull

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

// Environment represents the target Webull deployment environment.
type Environment string

const (
	EnvSandbox Environment = "SANDBOX"
	EnvLive    Environment = "LIVE"
)

// Credentials holds OpenAPI authentication credentials for Webull.
type Credentials struct {
	AppKey      string      `json:"app_key"`
	AppSecret   string      `json:"app_secret"`
	AccountID   string      `json:"account_id"`
	Environment Environment `json:"environment"`
}

// Validate checks that mandatory credentials are present and meet minimum formatting requirements.
func (c *Credentials) Validate() error {
	if strings.TrimSpace(c.AppKey) == "" {
		return errors.New("webull app_key is required")
	}
	if strings.TrimSpace(c.AppSecret) == "" {
		return errors.New("webull app_secret is required")
	}
	if c.Environment != EnvSandbox && c.Environment != EnvLive {
		return fmt.Errorf("invalid webull environment %q: must be SANDBOX or LIVE", c.Environment)
	}
	return nil
}

// Signer handles Webull OpenAPI canonical request building and HMAC-SHA256 signature generation.
type Signer struct {
	creds Credentials
}

// NewSigner creates a new Webull OpenAPI request signer.
func NewSigner(creds Credentials) (*Signer, error) {
	if err := creds.Validate(); err != nil {
		return nil, fmt.Errorf("invalid webull credentials: %w", err)
	}
	return &Signer{creds: creds}, nil
}

// GenerateNonce produces a cryptographically secure random hexadecimal nonce string.
func GenerateNonce(length int) (string, error) {
	if length <= 0 {
		length = 16
	}
	bytes := make([]byte, length)
	if _, err := rand.Read(bytes); err != nil {
		return "", fmt.Errorf("failed to generate random nonce: %w", err)
	}
	return hex.EncodeToString(bytes), nil
}

// FormatTimestamp returns an RFC3339 UTC timestamp string.
func FormatTimestamp(t time.Time) string {
	return t.UTC().Format(time.RFC3339)
}

// BuildCanonicalQuery sorts query parameters alphabetically by key and constructs a deterministic query string.
func BuildCanonicalQuery(params url.Values) string {
	if len(params) == 0 {
		return ""
	}
	keys := make([]string, 0, len(params))
	for k := range params {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	var pairs []string
	for _, k := range keys {
		vals := params[k]
		sort.Strings(vals)
		for _, v := range vals {
			pairs = append(pairs, fmt.Sprintf("%s=%s", url.QueryEscape(k), url.QueryEscape(v)))
		}
	}
	return strings.Join(pairs, "&")
}

// BuildCanonicalString constructs the deterministic payload string to be hashed and signed.
// Canonical Format:
// METHOD\n
// PATH\n
// CANONICAL_QUERY_STRING\n
// BODY_SHA256_HEX\n
// TIMESTAMP\n
// NONCE
func BuildCanonicalString(method, path string, query url.Values, body []byte, timestamp, nonce string) string {
	methodNorm := strings.ToUpper(strings.TrimSpace(method))
	pathNorm := strings.TrimSpace(path)
	if !strings.HasPrefix(pathNorm, "/") {
		pathNorm = "/" + pathNorm
	}

	canonicalQuery := BuildCanonicalQuery(query)

	bodyHash := sha256.Sum256(body)
	bodyHashHex := hex.EncodeToString(bodyHash[:])

	parts := []string{
		methodNorm,
		pathNorm,
		canonicalQuery,
		bodyHashHex,
		timestamp,
		nonce,
	}

	return strings.Join(parts, "\n")
}

// Sign computes the HMAC-SHA256 signature for a request and returns both the Base64 signature and canonical string.
func (s *Signer) Sign(method, path string, query url.Values, body []byte, timestamp, nonce string) (signature string, canonicalString string, err error) {
	if timestamp == "" {
		return "", "", errors.New("timestamp cannot be empty")
	}
	if nonce == "" {
		return "", "", errors.New("nonce cannot be empty")
	}

	canonicalString = BuildCanonicalString(method, path, query, body, timestamp, nonce)

	mac := hmac.New(sha256.New, []byte(s.creds.AppSecret))
	mac.Write([]byte(canonicalString))
	rawSig := mac.Sum(nil)
	signature = base64.StdEncoding.EncodeToString(rawSig)

	return signature, canonicalString, nil
}

// ApplyHeaders attaches standard Webull OpenAPI authentication headers to an HTTP request.
func (s *Signer) ApplyHeaders(req *http.Request, body []byte, now time.Time) error {
	if req == nil {
		return errors.New("http.Request cannot be nil")
	}

	nonce, err := GenerateNonce(16)
	if err != nil {
		return err
	}

	timestamp := FormatTimestamp(now)
	sig, _, err := s.Sign(req.Method, req.URL.Path, req.URL.Query(), body, timestamp, nonce)
	if err != nil {
		return fmt.Errorf("failed to compute OpenAPI signature: %w", err)
	}

	req.Header.Set("App-Key", s.creds.AppKey)
	req.Header.Set("Timestamp", timestamp)
	req.Header.Set("Nonce", nonce)
	req.Header.Set("Signature", sig)
	req.Header.Set("Signature-Method", "HMAC-SHA256")
	req.Header.Set("Content-Type", "application/json; charset=utf-8")
	req.Header.Set("Accept", "application/json")

	if s.creds.AccountID != "" {
		req.Header.Set("Account-Id", s.creds.AccountID)
	}

	return nil
}
