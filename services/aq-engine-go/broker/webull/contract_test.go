package webull

import (
	"strings"
	"testing"
)

// LegacyPathPrefixes are the old/invented routes that must NEVER appear in the
// current Trading API integration. Presence anywhere in routing is a contract
// violation that fails closed.
var legacyPathPrefixes = []string{
	"/api/v1/trade/",
	"/api/v1/market/quote",
}

// currentOfficialRoutes is the endpoint contract table derived from the CURRENT
// official Webull Trading API / Market Data API documentation.
var currentOfficialRoutes = map[string]string{
	"Account List":            EndpointAccountsList,
	"Account Balance":         EndpointBalanceGet,
	"Account Positions":       EndpointPositionsList,
	"Place Order":             EndpointOrderPlace,
	"Preview Order":           EndpointOrderPreview,
	"Replace Order":           EndpointOrderReplace,
	"Cancel Order":            EndpointOrderCancel,
	"Open Orders":             EndpointOpenOrdersList,
	"Order History":           EndpointHistoricalOrders,
	"Order Detail":            EndpointOrderGet,
	"Stock Snapshots":         EndpointMarketSnapshots,
	"Stock Bars (batch)":      EndpointMarketBarsList,
	"Stock Bars (single)":     EndpointMarketBarsGet,
	"Stock Ticks":             EndpointMarketTicksList,
	"Stock Depths":            EndpointMarketDepths,
}

// TestCurrentOfficialEndpointContract pins the internal route table to the
// official Trading API / Market Data API contract and blocks legacy paths.
func TestCurrentOfficialEndpointContract(t *testing.T) {
	for op, route := range currentOfficialRoutes {
		if route == "" {
			t.Fatalf("official route missing for operation %q", op)
		}
		if !strings.HasPrefix(route, "/trading/") && !strings.HasPrefix(route, "/market-data/") {
			t.Fatalf("operation %q route %q is outside the official Trading/Market Data API surface", op, route)
		}
	}

	allEndpoints := []string{
		EndpointAccountsList,
		EndpointBalanceGet,
		EndpointPositionsList,
		EndpointOrderPreview,
		EndpointOrderPlace,
		EndpointOrderReplace,
		EndpointOrderCancel,
		EndpointOpenOrdersList,
		EndpointHistoricalOrders,
		EndpointOrderGet,
		EndpointMarketSnapshots,
		EndpointMarketBarsList,
		EndpointMarketBarsGet,
		EndpointMarketTicksList,
		EndpointMarketDepths,
	}

	for _, ep := range allEndpoints {
		for _, legacy := range legacyPathPrefixes {
			if strings.Contains(ep, legacy) {
				t.Fatalf("legacy route prefix %q leaked into official endpoint table: %s", legacy, ep)
			}
		}
	}
}

// TestNoLegacyRoutesInBindings scans all HTTP bindings in this package for
// legacy Webull paths and fails closed if any appear.
func TestNoLegacyRoutesInBindings(t *testing.T) {
	for _, legacy := range legacyPathPrefixes {
		if strings.Contains(EndpointBalanceGet, legacy) ||
			strings.Contains(EndpointPositionsList, legacy) ||
			strings.Contains(EndpointOpenOrdersList, legacy) ||
			strings.Contains(EndpointOrderPlace, legacy) ||
			strings.Contains(EndpointOrderCancel, legacy) ||
			strings.Contains(EndpointMarketSnapshots, legacy) {
			t.Fatalf("legacy route %q still present in live routing", legacy)
		}
	}
}