package webull

import (
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"
)

// parseRequiredDecimal parses an authoritative numeric string field that the
// Webull contract requires. An empty or malformed value is an error: zero is
// never invented for authoritative broker state.
func parseRequiredDecimal(field, raw string) (float64, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return 0, fmt.Errorf("webull field %q is required but was empty", field)
	}
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return 0, fmt.Errorf("webull field %q is malformed numeric value %q", field, raw)
	}
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return 0, fmt.Errorf("webull field %q is not finite: %q", field, raw)
	}
	return v, nil
}

// parseOptionalDecimal parses an optional numeric field. Absent (empty) returns
// (nil, nil); present-but-malformed returns an error. Zero is never invented.
func parseOptionalDecimal(field, raw string) (*float64, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, nil
	}
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return nil, fmt.Errorf("webull field %q is malformed numeric value %q", field, raw)
	}
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return nil, fmt.Errorf("webull field %q is not finite: %q", field, raw)
	}
	return &v, nil
}

// parseRequiredTimestamp parses an authoritative timestamp that is either
// RFC3339 or Unix epoch milliseconds. A malformed timestamp is an error; the
// caller must never substitute time.Now() for authoritative broker freshness.
func parseRequiredTimestamp(field, raw string) (time.Time, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return time.Time{}, fmt.Errorf("webull field %q is required but was empty", field)
	}
	if t, err := time.Parse(time.RFC3339, raw); err == nil {
		return t.UTC(), nil
	}
	if ms, err := strconv.Atoi(raw); err == nil && ms > 0 {
		return time.UnixMilli(int64(ms)).UTC(), nil
	}
	return time.Time{}, fmt.Errorf("webull field %q is malformed timestamp %q", field, raw)
}

// nonEmptyValue returns the value when it is non-zero and parseable, otherwise feeds a sentinel. It exists to keep
// nil-pointer handling explicit at call sites only; prefer parseOptionalDecimal directly.
func decimalOrFallback(opt *float64, fallback float64) float64 {
	if opt == nil {
		return fallback
	}
	return *opt
}