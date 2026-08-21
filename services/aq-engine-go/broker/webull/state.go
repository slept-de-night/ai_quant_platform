package webull

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
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

// WebullPositionLeg is a single leg of a multi-leg position (options). Official
// positions may carry a nested `legs` array; only leg_id/symbol/quantity are
// relevant to normalized broker truth.
type WebullPositionLeg struct {
	LegID   string `json:"leg_id"`
	Symbol  string `json:"symbol"`
	Quantity string `json:"quantity"`
}

// WebullPositionItem reflects the CURRENT official Webull Trading API account
// position response schema (v2.0). Quantities and prices are string-typed and
// fractional quantities are supported — never truncate them to integers.
type WebullPositionItem struct {
	PositionID           string              `json:"position_id"`
	Currency             string              `json:"currency"`
	Quantity             string              `json:"quantity"`
	Symbol               string              `json:"symbol"`
	InstrumentType       string              `json:"instrument_type"`
	LastPrice            string              `json:"last_price"`
	CostPrice            string              `json:"cost_price"`
	UnrealizedProfitLoss string              `json:"unrealized_profit_loss"`
	OptionStrategy       string              `json:"option_strategy"`
	EventOutcome         string              `json:"event_outcome"`
	Legs                 []WebullPositionLeg `json:"legs"`
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

	cash, err := parseRequiredDecimal("total_cash_balance", raw.TotalCashBalance)
	if err != nil {
		return nil, err
	}
	equity, err := parseRequiredDecimal("total_net_liquidation_value", raw.TotalNetLiquidationValue)
	if err != nil {
		return nil, err
	}

	curr := raw.TotalAssetCurrency
	if curr == "" {
		curr = "USD"
	}

	var bp float64
	bpSet := false
	for _, asset := range raw.AccountCurrencyAssets {
		if asset.Currency == curr {
			parsed, err := parseOptionalDecimal("buying_power", asset.BuyingPower)
			if err != nil {
				return nil, err
			}
			if parsed != nil {
				bp, bpSet = *parsed, true
			}
			break
		}
	}
	if !bpSet {
		for _, asset := range raw.AccountCurrencyAssets {
			if asset.Currency == "" {
				parsed, err := parseOptionalDecimal("buying_power", asset.BuyingPower)
				if err != nil {
					return nil, err
				}
				if parsed != nil {
					bp = *parsed
				}
				break
			}
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
//
// The official position schema does not include market_value or cost_basis in a
// broker-returned form; it returns quantity, last_price, and cost_price. Market
// value and cost basis are DERIVED (quantity * last_price and quantity *
// cost_price) ONLY when both operands are present and valid. If quantity is valid
// but price is absent/malformed, the derived field is left at 0 (never invented);
// the exact broker quantity is always preserved.
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
		if item.Symbol == "" {
			return nil, fmt.Errorf("webull position is missing symbol")
		}
		qty, err := parseRequiredDecimal("quantity", item.Quantity)
		if err != nil {
			return nil, err
		}

		// Derive market value / cost basis from (quantity * price) only when both
		// are present and valid. last_price and cost_price are optional per the
		// official schema, so a malformed price is an error but an absent price
		// simply leaves the derived field at 0 (never invented).
		var marketValue, costBasis float64
		lastPrice, err := parseOptionalDecimal("last_price", item.LastPrice)
		if err != nil {
			return nil, err
		}
		if lastPrice != nil {
			marketValue = qty * *lastPrice
		}
		costPrice, err := parseOptionalDecimal("cost_price", item.CostPrice)
		if err != nil {
			return nil, err
		}
		if costPrice != nil {
			costBasis = qty * *costPrice
		}

		positions = append(positions, broker.BrokerPosition{
			Symbol:      item.Symbol,
			Qty:         qty,
			MarketValue: marketValue,
			CostBasis:   costBasis,
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
		totalQty, err := parseRequiredDecimal("total_quantity", item.TotalQty)
		if err != nil {
			return nil, err
		}
		filledQty, err := parseRequiredDecimal("filled_quantity", item.FilledQty)
		if err != nil {
			return nil, err
		}
		avgPrice, err := parseOptionalDecimal("avg_price", item.AvgPrice)
		if err != nil {
			return nil, err
		}
		if filledQty > 0 && avgPrice == nil {
			return nil, fmt.Errorf("webull order %s is filled but avg_price is absent", item.OrderID)
		}
		limitPrice, err := parseOptionalDecimal("limit_price", item.LimitPrice)
		if err != nil {
			return nil, err
		}

		status := strings.TrimSpace(item.Status)
		if status == "" {
			return nil, fmt.Errorf("webull order %s is missing status", item.OrderID)
		}
		normStatus := broker.NormalizeBrokerStatus(status)

		createdAt, err := parseRequiredTimestamp("create_time", item.CreateTime)
		if err != nil {
			return nil, err
		}
		updatedAt, err := parseRequiredTimestamp("update_time", item.UpdateTime)
		if err != nil {
			return nil, err
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
			AverageFillPrice: decimalOrFallback(avgPrice, 0),
			AvgPrice:         decimalOrFallback(avgPrice, 0),
			LimitPrice:       decimalOrFallback(limitPrice, 0),
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
			RequestedQty:  o.RequestedQty,
			FilledQty:     o.FilledQtyFloat,
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
