package auth

import (
	"log"
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
