package webull

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"strconv"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/reconciliation"
)

// Webull raw JSON response schemas
//
// These reflect the CURRENT official Webull Trading API contract. Account
// balances are exposed via a top-level summary plus per-currency asset arrays.

type WebullAccountCurrencyAsset struct {
	Currency             string `json:"currency"`
	CashBalance          string `json:"cash_balance"`
	BuyingPower          string `json:"buying_power"`
	DayBuyingPower       string `json:"day_buying_power"`
	OvernightBuyingPower string `json:"overnight_buying_power"`
	DayProfitLoss        string `json:"day_profit_loss"`
	NetLiquidationValue  string `json:"net_liquidation_value"`
}

type WebullAccountResponse struct {
	TotalAssetCurrency        string                        `json:"total_asset_currency"`
	TotalCurrencyBalance      string                        `json:"total_currency_balance"`
	TotalCashBalance          string                        `json:"total_cash_balance"`
	TotalMarketValue          string                        `json:"total_market_value"`
	TotalUnrealizedProfitLoss string                        `json:"total_unrealized_profit_loss"`
	TotalNetLiquidationValue  string                        `json:"total_net_liquidation_value"`
	TotalDayProfitLoss        string                        `json:"total_day_profit_loss"`
	AccountCurrencyAssets     []WebullAccountCurrencyAsset  `json:"account_currency_assets"`
}

type WebullPositionItem struct {
	Symbol      string `json:"symbol"`
	Quantity    string `json:"quantity"`
	MarketValue string `json:"market_value"`
	CostBasis   string `json:"cost_basis"`
	LastPrice   string `json:"last_price"`
}

type WebullOrderItem struct {
	OrderID         string `json:"order_id"`
	ClientOrderID   string `json:"client_order_id"`
	Symbol          string `json:"symbol"`
	Side            string `json:"side"` // "BUY", "SELL"
	TotalQty        string `json:"total_quantity"`
	FilledQty       string `json:"filled_quantity"`
	AvgPrice        string `json:"avg_price"`
	LimitPrice      string `json:"limit_price"`
	Status          string `json:"status"` // "SUBMITTED", "FILLED", "CANCELLED", "FAILED", etc.
	CreateTime      string `json:"create_time"`
	UpdateTime      string `json:"update_time"`
}

// parseFloatSafe parses string numeric representation safely, defaulting to 0.0 on error.
func parseFloatSafe(s string) float64 {
	if s == "" {
		return 0.0
	}
	val, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0.0
	}
	return val
}

// FetchAccount queries the Webull OpenAPI account endpoint and returns normalized AccountState.
func FetchAccount(ctx context.Context, client *Client, accountID string) (*broker.AccountState, error) {
	if client == nil {
		return nil, fmt.Errorf("webull client is nil")
	}

	query := url.Values{}
	if accountID != "" {
		query.Set("account_id", accountID)
	}

	code, body, err := client.Execute(ctx, "GET", EndpointBalanceGet, query, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch webull account (HTTP %d): %w", code, err)
	}

	var raw WebullAccountResponse
	if err := json.Unmarshal(body, &raw); err != nil {
		return nil, fmt.Errorf("failed to parse webull account response: %w", err)
	}

	cash := parseFloatSafe(raw.TotalCashBalance)
	equity := parseFloatSafe(raw.TotalNetLiquidationValue)
	curr := raw.TotalAssetCurrency
	if curr == "" {
		curr = "USD"
	}

	bp := 0.0
	for _, asset := range raw.AccountCurrencyAssets {
		if asset.Currency == "" || asset.Currency == curr {
			bp = parseFloatSafe(asset.BuyingPower)
			break
		}
	}

	return &broker.AccountState{
		Cash:        cash,
		Equity:      equity,
		BuyingPower: bp,
		Currency:    curr,
	}, nil
}

// FetchPositions queries the Webull OpenAPI positions endpoint and returns normalized BrokerPositions.
func FetchPositions(ctx context.Context, client *Client, accountID string) ([]broker.BrokerPosition, error) {
	if client == nil {
		return nil, fmt.Errorf("webull client is nil")
	}

	query := url.Values{}
	if accountID != "" {
		query.Set("account_id", accountID)
	}

	code, body, err := client.Execute(ctx, "GET", EndpointPositionsList, query, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch webull positions (HTTP %d): %w", code, err)
	}

	var rawItems []WebullPositionItem
	if err := json.Unmarshal(body, &rawItems); err != nil {
		return nil, fmt.Errorf("failed to parse webull positions response: %w", err)
	}

	positions := make([]broker.BrokerPosition, 0, len(rawItems))
	for _, item := range rawItems {
		qty := parseFloatSafe(item.Quantity)
		mv := parseFloatSafe(item.MarketValue)
		cost := parseFloatSafe(item.CostBasis)

		positions = append(positions, broker.BrokerPosition{
			Symbol:      item.Symbol,
			Qty:         qty,
			MarketValue: mv,
			CostBasis:   cost,
		})
	}

	return positions, nil
}

// FetchOrders queries the Webull OpenAPI orders endpoint and returns normalized BrokerOrders.
func FetchOrders(ctx context.Context, client *Client, accountID string) ([]broker.BrokerOrder, error) {
	if client == nil {
		return nil, fmt.Errorf("webull client is nil")
	}

	query := url.Values{}
	if accountID != "" {
		query.Set("account_id", accountID)
	}

	code, body, err := client.Execute(ctx, "GET", EndpointOpenOrdersList, query, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch webull orders (HTTP %d): %w", code, err)
	}

	var rawItems []WebullOrderItem
	if err := json.Unmarshal(body, &rawItems); err != nil {
		return nil, fmt.Errorf("failed to parse webull orders response: %w", err)
	}

	orders := make([]broker.BrokerOrder, 0, len(rawItems))
	for _, item := range rawItems {
		totalQty := parseFloatSafe(item.TotalQty)
		filledQty := parseFloatSafe(item.FilledQty)
		avgPrice := parseFloatSafe(item.AvgPrice)
		limitPrice := parseFloatSafe(item.LimitPrice)

		normStatus := broker.NormalizeBrokerStatus(item.Status)

		createdAt := time.Now().UTC()
		if t, err := time.Parse(time.RFC3339, item.CreateTime); err == nil {
			createdAt = t
		}
		updatedAt := createdAt
		if t, err := time.Parse(time.RFC3339, item.UpdateTime); err == nil {
			updatedAt = t
		}

		orders = append(orders, broker.BrokerOrder{
			ID:               item.OrderID,
			BrokerOrderID:    item.OrderID,
			ClientOrderID:    item.ClientOrderID,
			Symbol:           item.Symbol,
			Side:             item.Side,
			Qty:              int(totalQty),
			RequestedQty:     totalQty,
			FilledQty:        int(filledQty),
			FilledQtyFloat:   filledQty,
			AverageFillPrice: avgPrice,
			AvgPrice:         avgPrice,
			LimitPrice:       limitPrice,
			Status:           normStatus,
			RawStatus:        item.Status,
			CreatedAt:        createdAt,
			UpdatedAt:        updatedAt,
		})
	}

	return orders, nil
}

// FetchBrokerSnapshot queries account, positions, and open orders to construct a reconciliation snapshot.
func FetchBrokerSnapshot(ctx context.Context, client *Client, accountID string) (*reconciliation.BrokerState, error) {
	account, err := FetchAccount(ctx, client, accountID)
	if err != nil {
		return nil, fmt.Errorf("snapshot account query failed: %w", err)
	}

	positions, err := FetchPositions(ctx, client, accountID)
	if err != nil {
		return nil, fmt.Errorf("snapshot positions query failed: %w", err)
	}

	orders, err := FetchOrders(ctx, client, accountID)
	if err != nil {
		return nil, fmt.Errorf("snapshot orders query failed: %w", err)
	}

	posMap := make(map[string]reconciliation.PositionState)
	for _, p := range positions {
		posMap[p.Symbol] = reconciliation.PositionState{
			Symbol:      p.Symbol,
			Qty:         p.Qty,
			MarketValue: p.MarketValue,
			CostBasis:   p.CostBasis,
		}
	}

	ordMap := make(map[string]reconciliation.OrderState)
	for _, o := range orders {
		cID := o.ClientOrderID
		if cID == "" {
			cID = o.BrokerOrderID
		}
		ordMap[cID] = reconciliation.OrderState{
			ClientOrderID: o.ClientOrderID,
			BrokerOrderID: o.BrokerOrderID,
			Symbol:        o.Symbol,
			Side:          o.Side,
			RequestedQty:  o.Qty,
			FilledQty:     o.FilledQty,
			Status:        string(o.Status),
			CreatedAt:     o.CreatedAt,
			UpdatedAt:     o.UpdatedAt,
		}
	}

	return &reconciliation.BrokerState{
		Orders:    ordMap,
		Positions: posMap,
		Cash:      account.Cash,
		Equity:    account.Equity,
		Timestamp: time.Now().UTC(),
	}, nil
}
