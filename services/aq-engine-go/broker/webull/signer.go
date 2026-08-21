package webull

import (
	"crypto/hmac"
	"crypto/md5"
	"crypto/rand"
	"crypto/sha1"
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

// OpenAPI signing constants per official Webull documentation.
const (
	SignatureAlgorithm = "HMAC-SHA1"
	SignatureVersion   = "1.0"
	APIVersion         = "v2"
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
	AccessToken string      `json:"access_token,omitempty"`
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

// Signer handles Webull OpenAPI canonical request building and official HMAC-SHA1 signature generation.
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

// FormatTimestamp returns an RFC3339 UTC timestamp string (YYYY-MM-DDThh:mm:ssZ).
func FormatTimestamp(t time.Time) string {
	return t.UTC().Format(time.RFC3339)
}

// percentEncodeAll percent-encodes every byte except the RFC 3986 unreserved set.
// This matches the official URL-encoding of the complete signing string (safe="").
func percentEncodeAll(s string) string {
	const hexDigits = "0123456789ABCDEF"
	var b strings.Builder
	b.Grow(len(s))
	for i := 0; i < len(s); i++ {
		c := s[i]
		if (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
			c == '-' || c == '.' || c == '_' || c == '~' {
			b.WriteByte(c)
			continue
		}
		b.WriteByte('%')
		b.WriteByte(hexDigits[c>>4])
		b.WriteByte(hexDigits[c&0x0F])
	}
	return b.String()
}

// buildSigningString constructs str1: query parameters merged with the official
// signing headers, sorted ascending by name and joined as key=value&key=value...
func (s *Signer) buildSigningString(query url.Values, host, timestamp, nonce string) string {
	items := make(map[string]string, len(query)+6)
	for k, vals := range query {
		vals = append([]string(nil), vals...)
		sort.Strings(vals)
		items[k] = strings.Join(vals, "&")
	}
	items["x-app-key"] = s.creds.AppKey
	items["x-timestamp"] = timestamp
	items["x-signature-algorithm"] = SignatureAlgorithm
	items["x-signature-version"] = SignatureVersion
	items["x-signature-nonce"] = nonce
	items["host"] = host

	keys := make([]string, 0, len(items))
	for k := range items {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	pairs := make([]string, 0, len(keys))
	for _, k := range keys {
		pairs = append(pairs, k+"="+items[k])
	}
	return strings.Join(pairs, "&")
}

// Sign computes the official HMAC-SHA1 OpenAPI signature for a request.
//
// Algorithm (official Webull documentation):
//
//  1. Merge query params + signing headers (x-app-key, x-signature-algorithm,
//     x-signature-version, x-signature-nonce, x-timestamp, host).
//  2. Sort names ascending.
//  3. Join as key=value&key=value... -> str1.
//  4. If body exists, compute uppercase MD5 hex of the body -> str2.
//  5. str3 = path + "&" + str1 [+ "&" + str2].
//  6. URL-encode the complete signing string.
//  7. Signing key = appSecret + "&".
//  8. Signature = Base64(HMAC-SHA1(signingKey, encodedString)).
func (s *Signer) Sign(host, path string, query url.Values, body []byte, timestamp, nonce string) (signature string, canonicalString string, err error) {
	if strings.TrimSpace(host) == "" {
		return "", "", errors.New("host cannot be empty")
	}
	if strings.TrimSpace(path) == "" {
		return "", "", errors.New("path cannot be empty")
	}
	if timestamp == "" {
		return "", "", errors.New("timestamp cannot be empty")
	}
	if nonce == "" {
		return "", "", errors.New("nonce cannot be empty")
	}

	str1 := s.buildSigningString(query, host, timestamp, nonce)

	var str3 string
	if len(body) > 0 {
		sum := md5.Sum(body)
		str2 := strings.ToUpper(hex.EncodeToString(sum[:]))
		str3 = path + "&" + str1 + "&" + str2
	} else {
		str3 = path + "&" + str1
	}

	encoded := percentEncodeAll(str3)

	signingKey := s.creds.AppSecret + "&"
	mac := hmac.New(sha1.New, []byte(signingKey))
	mac.Write([]byte(encoded))
	rawSig := mac.Sum(nil)
	signature = base64.StdEncoding.EncodeToString(rawSig)

	return signature, str3, nil
}

// ApplyHeaders attaches official Webull OpenAPI authentication headers to an HTTP request.
func (s *Signer) ApplyHeaders(req *http.Request, body []byte, now time.Time) error {
	if req == nil {
		return errors.New("http.Request cannot be nil")
	}

	nonce, err := GenerateNonce(16)
	if err != nil {
		return err
	}

	timestamp := FormatTimestamp(now)
	sig, _, err := s.Sign(req.URL.Host, req.URL.Path, req.URL.Query(), body, timestamp, nonce)
	if err != nil {
		return fmt.Errorf("failed to compute OpenAPI signature: %w", err)
	}

	req.Header.Set("x-app-key", s.creds.AppKey)
	req.Header.Set("x-timestamp", timestamp)
	req.Header.Set("x-signature", sig)
	req.Header.Set("x-signature-algorithm", SignatureAlgorithm)
	req.Header.Set("x-signature-version", SignatureVersion)
	req.Header.Set("x-signature-nonce", nonce)
	req.Header.Set("x-version", APIVersion)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	if s.creds.AccessToken != "" {
		req.Header.Set("x-access-token", s.creds.AccessToken)
	}

	return nil
}