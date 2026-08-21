package webull

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// Official OpenAPI Base URLs (environment is explicit; never inferred from URL text).
const (
	SandboxBaseURL = "https://api.sandbox.webull.com"
	LiveBaseURL    = "https://api.webull.com"
)

// Custom error types
var (
	ErrRateLimitExceeded   = errors.New("webull api rate limit exceeded (HTTP 429)")
	ErrAuthenticationFail  = errors.New("webull authentication failed (HTTP 401/403)")
	ErrServerUnavailable   = errors.New("webull upstream server unavailable (HTTP 5xx)")
	ErrAmbiguousTransport  = errors.New("webull transport ambiguity: timeout or network disruption during in-flight request")
)

// TokenBucketRateLimiter implements a concurrent token bucket rate limiter.
type TokenBucketRateLimiter struct {
	mu         sync.Mutex
	capacity   float64
	tokens     float64
	refillRate float64 // tokens per second
	lastRefill time.Time
}

func NewTokenBucketRateLimiter(ratePerSec float64, capacity float64) *TokenBucketRateLimiter {
	if ratePerSec <= 0 {
		ratePerSec = 10.0
	}
	if capacity <= 0 {
		capacity = 20.0
	}
	return &TokenBucketRateLimiter{
		capacity:   capacity,
		tokens:     capacity,
		refillRate: ratePerSec,
		lastRefill: time.Now().UTC(),
	}
}

func (tb *TokenBucketRateLimiter) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now().UTC()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens = tb.tokens + elapsed*tb.refillRate
	if tb.tokens > tb.capacity {
		tb.tokens = tb.capacity
	}
	tb.lastRefill = now

	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}

// Client provides an HTTP client with OpenAPI request signing, rate limiting, and exponential backoff.
type Client struct {
	creds          Credentials
	signer         *Signer
	httpClient     *http.Client
	baseURL        string
	rateLimiter    *TokenBucketRateLimiter
	maxRetries     int
	initialBackoff time.Duration
	maxBackoff     time.Duration
}

// ClientOption allows customizing client behavior.
type ClientOption func(*Client)

func WithHTTPClient(hc *http.Client) ClientOption {
	return func(c *Client) {
		if hc != nil {
			c.httpClient = hc
		}
	}
}

func WithBaseURL(u string) ClientOption {
	return func(c *Client) {
		if u != "" {
			c.baseURL = strings.TrimRight(u, "/")
		}
	}
}

func WithMaxRetries(retries int) ClientOption {
	return func(c *Client) {
		if retries >= 0 {
			c.maxRetries = retries
		}
	}
}

func WithBackoff(initial, max time.Duration) ClientOption {
	return func(c *Client) {
		if initial > 0 {
			c.initialBackoff = initial
		}
		if max > 0 {
			c.maxBackoff = max
		}
	}
}

// NewClient initializes a Webull OpenAPI HTTP Client.
func NewClient(creds Credentials, opts ...ClientOption) (*Client, error) {
	signer, err := NewSigner(creds)
	if err != nil {
		return nil, err
	}

	baseURL := LiveBaseURL
	if creds.Environment == EnvSandbox {
		baseURL = SandboxBaseURL
	}

	c := &Client{
		creds:          creds,
		signer:         signer,
		httpClient:     &http.Client{Timeout: 10 * time.Second},
		baseURL:        baseURL,
		rateLimiter:    NewTokenBucketRateLimiter(10.0, 20.0),
		maxRetries:     3,
		initialBackoff: 100 * time.Millisecond,
		maxBackoff:     2 * time.Second,
	}

	for _, opt := range opts {
		opt(c)
	}

	return c, nil
}

// RedactLogMessage redacts secret keys, signatures, and tokens from log messages.
func (c *Client) RedactLogMessage(msg string) string {
	redacted := msg
	if c.creds.AppSecret != "" {
		redacted = strings.ReplaceAll(redacted, c.creds.AppSecret, "[REDACTED_APP_SECRET]")
	}
	if c.creds.AppKey != "" {
		// Only redact full app key if length >= 8
		if len(c.creds.AppKey) >= 8 {
			redacted = strings.ReplaceAll(redacted, c.creds.AppKey, "[REDACTED_APP_KEY]")
		}
	}
	return redacted
}

// doAttempt performs a single signed HTTP request attempt. It returns the
// HTTP status, response body, and a classified error. Transport errors that
// are ambiguous (timeout/disconnect without a definitive broker rejection) are
// wrapped in ErrAmbiguousTransport so callers can decide whether to retry.
func (c *Client) doAttempt(ctx context.Context, method, path string, query url.Values, body []byte) (*http.Response, []byte, error) {
	req, err := http.NewRequestWithContext(ctx, method, path, bytes.NewReader(body))
	if err != nil {
		return nil, nil, fmt.Errorf("failed to create request: %w", err)
	}

	if err := c.signer.ApplyHeaders(req, body, time.Now().UTC()); err != nil {
		return nil, nil, fmt.Errorf("failed to sign request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
			return nil, nil, fmt.Errorf("%w: %v", ErrAmbiguousTransport, err)
		}
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
			return nil, nil, fmt.Errorf("%w: %v", ErrAmbiguousTransport, err)
		}
		return nil, nil, err
	}

	respBody, readErr := io.ReadAll(resp.Body)
	resp.Body.Close()
	if readErr != nil {
		return resp, nil, fmt.Errorf("failed to read response body: %w", readErr)
	}
	return resp, respBody, nil
}

// Execute performs a read-safe authenticated HTTP request with bounded retries.
// It may be used for idempotent reads (GET balances/positions/orders, market
// snapshot) but must NEVER be used for economic writes.
func (c *Client) Execute(ctx context.Context, method, path string, query url.Values, body []byte) (int, []byte, error) {
	if ctx == nil {
		ctx = context.Background()
	}

	if c.rateLimiter != nil && !c.rateLimiter.Allow() {
		return 0, nil, ErrRateLimitExceeded
	}

	fullURL := c.baseURL + path
	if len(query) > 0 {
		fullURL += "?" + query.Encode()
	}

	var lastErr error
	backoff := c.initialBackoff

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			jitter := time.Duration(rand.Int63n(int64(backoff / 2)))
			sleepDuration := backoff + jitter
			select {
			case <-ctx.Done():
				return 0, nil, ctx.Err()
			case <-time.After(sleepDuration):
			}
			backoff *= 2
			if backoff > c.maxBackoff {
				backoff = c.maxBackoff
			}
		}

		resp, respBody, e := c.doAttempt(ctx, method, fullURL, query, body)
		if e != nil {
			lastErr = e
			log.Printf("[WEBULL HTTP ERROR] %s", c.RedactLogMessage(fmt.Sprintf("%s %s (attempt %d/%d) transport error: %v", method, path, attempt+1, c.maxRetries+1, e)))
			continue
		}

		switch {
		case resp.StatusCode >= 200 && resp.StatusCode < 300:
			return resp.StatusCode, respBody, nil

		case resp.StatusCode == http.StatusTooManyRequests:
			lastErr = fmt.Errorf("%w: response=%s", ErrRateLimitExceeded, string(respBody))
			log.Printf("[WEBULL RATE LIMIT 429] %s (attempt %d/%d)", c.RedactLogMessage(fmt.Sprintf("%s %s", method, path)), attempt+1, c.maxRetries+1)
			continue

		case resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden:
			return resp.StatusCode, respBody, fmt.Errorf("%w (HTTP %d): %s", ErrAuthenticationFail, resp.StatusCode, string(respBody))

		case resp.StatusCode >= 500 && resp.StatusCode < 600:
			lastErr = fmt.Errorf("%w (HTTP %d): response=%s", ErrServerUnavailable, resp.StatusCode, string(respBody))
			log.Printf("[WEBULL SERVER ERROR 5XX] %s (HTTP %d, attempt %d/%d)", c.RedactLogMessage(fmt.Sprintf("%s %s", method, path)), resp.StatusCode, attempt+1, c.maxRetries+1)
			continue

		default:
			return resp.StatusCode, respBody, fmt.Errorf("webull api client error (HTTP %d): %s", resp.StatusCode, string(respBody))
		}
	}

	return 0, nil, fmt.Errorf("webull request failed after %d retries: %w", c.maxRetries, lastErr)
}

// ExecuteNoRetry performs a single-attempt authenticated HTTP request with NO
// automatic retry. This is required for economic writes (place/cancel/replace)
// where an automatic retry after an ambiguous transport failure could duplicate
// a broker event. Transport ambiguity surfaces as ErrAmbiguousTransport so the
// OMS can mark the submission SUBMISSION_UNKNOWN and reconcile via order detail.
func (c *Client) ExecuteNoRetry(ctx context.Context, method, path string, query url.Values, body []byte) (int, []byte, error) {
	if ctx == nil {
		ctx = context.Background()
	}

	if c.rateLimiter != nil && !c.rateLimiter.Allow() {
		return 0, nil, ErrRateLimitExceeded
	}

	fullURL := c.baseURL + path
	if len(query) > 0 {
		fullURL += "?" + query.Encode()
	}

	resp, respBody, e := c.doAttempt(ctx, method, fullURL, query, body)
	if e != nil {
		return 0, nil, e
	}

	switch {
	case resp.StatusCode >= 200 && resp.StatusCode < 300:
		return resp.StatusCode, respBody, nil

	case resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden:
		return resp.StatusCode, respBody, fmt.Errorf("%w (HTTP %d): %s", ErrAuthenticationFail, resp.StatusCode, string(respBody))

	case resp.StatusCode >= 500 && resp.StatusCode < 600:
		return resp.StatusCode, respBody, fmt.Errorf("%w (HTTP %d): response=%s", ErrServerUnavailable, resp.StatusCode, string(respBody))

	default:
		return resp.StatusCode, respBody, fmt.Errorf("webull api client error (HTTP %d): %s", resp.StatusCode, string(respBody))
	}
}

// ExecuteRead is a semantic alias for Execute: a read-only, idempotent, safely
// retryable request. Prefer this name at read call sites for clarity.
func (c *Client) ExecuteRead(ctx context.Context, path string, query url.Values) (int, []byte, error) {
	return c.Execute(ctx, "GET", path, query, nil)
}

// Error classification predicates
func IsRateLimited(err error) bool {
	return errors.Is(err, ErrRateLimitExceeded)
}

func IsAuthError(err error) bool {
	return errors.Is(err, ErrAuthenticationFail)
}

func IsServerError(err error) bool {
	return errors.Is(err, ErrServerUnavailable)
}

func IsAmbiguousTransportError(err error) bool {
	return errors.Is(err, ErrAmbiguousTransport)
}
