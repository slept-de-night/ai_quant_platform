package webull

// Official Webull OpenAPI Trading API / Market Data API endpoint contract.
//
// These are the CURRENT official Trading API (individual account) and Market
// Data API routes. They are the single source of truth for routing; keep this
// table in sync with the official Webull reference when the upstream contract
// changes.
const (
	// Trading API — account routes.
	EndpointAccountsList      = "/trading/accounts/list"
	EndpointBalanceGet        = "/trading/assets/balances/get"
	EndpointPositionsList     = "/trading/assets/positions/list"

	// Trading API — order routes.
	EndpointOrderPreview       = "/trading/orders/preview"
	EndpointOrderPlace         = "/trading/orders/place"
	EndpointOrderReplace       = "/trading/orders/replace"
	EndpointOrderCancel        = "/trading/orders/cancel"
	EndpointOpenOrdersList     = "/trading/orders/open-orders/list"
	EndpointHistoricalOrders   = "/trading/orders/historical-orders/list"
	EndpointOrderGet           = "/trading/orders/get"

	// Market Data API — stock routes.
	EndpointMarketSnapshots = "/market-data/stocks/snapshots/list"
	EndpointMarketBarsList  = "/market-data/stocks/bars/list"
	EndpointMarketBarsGet   = "/market-data/stocks/bars/get"
	EndpointMarketTicksList = "/market-data/stocks/ticks/list"
	EndpointMarketDepths    = "/market-data/stocks/depths/list"
)