package auth

import (
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"strings"
	"sync"
)

var (
	warnOnce sync.Once
)

// Middleware enforces API token authentication when configured or required.
func Middleware(configuredToken string, authRequired bool) func(http.Handler) http.Handler {
	trimmedToken := strings.TrimSpace(configuredToken)

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			path := r.URL.Path

			// Public operational endpoints: health and metrics
			if path == "/health" || path == "/metrics" || path == "/api/v1/metrics" {
				next.ServeHTTP(w, r)
				return
			}

			// If no token is configured and auth is not strictly required, allow with warning in dev
			if trimmedToken == "" && !authRequired {
				warnOnce.Do(func() {
					log.Printf("[SECURITY WARNING] AUTH_TOKEN not configured; control plane running in unprotected development mode")
				})
				next.ServeHTTP(w, r)
				return
			}

			// Check Authorization Header: Bearer <token>
			authHeader := r.Header.Get("Authorization")
			var providedToken string
			if strings.HasPrefix(authHeader, "Bearer ") {
				providedToken = strings.TrimSpace(strings.TrimPrefix(authHeader, "Bearer "))
			} else if apiKey := r.Header.Get("X-API-Key"); apiKey != "" {
				providedToken = strings.TrimSpace(apiKey)
			}

			if providedToken == "" || providedToken != trimmedToken {
				http.Error(w, `{"error":"unauthorized","message":"invalid or missing API authentication token"}`, http.StatusUnauthorized)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// ValidateEnvironmentCredentials verifies that credentials and authentication posture meet safety standards for the target environment.
func ValidateEnvironmentCredentials(execEnv string, authToken string, allowAnonymousLocal bool) error {
	envNorm := strings.ToLower(strings.TrimSpace(execEnv))
	trimmedToken := strings.TrimSpace(authToken)

	// Live / Real money mode: auth token is strictly mandatory and must meet entropy standards
	if envNorm == "live" || envNorm == "production" || envNorm == "real" {
		if trimmedToken == "" {
			return errors.New("FATAL: AUTH_TOKEN or ENGINE_API_KEY is required in live/production mode; anonymous access is strictly prohibited")
		}
		if len(trimmedToken) < 16 {
			return errors.New("FATAL: AUTH_TOKEN in live mode must be at least 16 characters for adequate entropy")
		}
		lower := strings.ToLower(trimmedToken)
		insecureSubstrings := []string{
			"admin", "password", "secret", "123456", "default", "changeme",
		}
		for _, bad := range insecureSubstrings {
			if strings.Contains(lower, bad) {
				return fmt.Errorf("FATAL: Insecure/default substring '%s' detected in live mode AUTH_TOKEN", bad)
			}
		}
		return nil
	}

	// Simulation / Paper mode
	if trimmedToken == "" && !allowAnonymousLocal {
		return errors.New("AUTH_TOKEN not configured and ALLOW_ANONYMOUS_LOCAL is false")
	}

	return nil
}

// GetListenAddress derives the secure network listening address.
// Defaults to loopback 127.0.0.1:8080, never 0.0.0.0:8080 unless explicitly configured.
func GetListenAddress(hostEnv, portEnv string) string {
	host := strings.TrimSpace(hostEnv)
	if host == "" {
		host = "127.0.0.1" // Secure default loopback binding
	}
	port := strings.TrimSpace(portEnv)
	if port == "" {
		port = "8080"
	}
	return net.JoinHostPort(host, port)
}

// RedactSecret replaces sensitive substrings in messages with [REDACTED].
func RedactSecret(msg string, secrets ...string) string {
	result := msg
	for _, sec := range secrets {
		if trimmed := strings.TrimSpace(sec); len(trimmed) > 3 {
			result = strings.ReplaceAll(result, trimmed, "[REDACTED]")
		}
	}
	return result
}
