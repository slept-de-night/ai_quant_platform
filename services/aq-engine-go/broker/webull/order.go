package webull

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/models"
)

// ErrLiveTradingNotPermitted enforces the real-money safety invariant blocking live order submission.
var ErrLiveTradingNotPermitted = errors.New("live order submission is strictly prohibited: Webull live trading release gates have not been met")

type PlaceOrderRequest struct {
	ClientOrderID string `json:"client_order_id"`
	AccountID     string `json:"account_id"`
	Symbol        string `json:"symbol"`
	Side          string `json:"side"`
	OrderType     string `json:"order_type"`
	Quantity      string `json:"quantity"`
	LimitPrice    string `json:"limit_price,omitempty"`
	TimeInForce   string `json:"time_in_force"`
}

type PlaceOrderResponse struct {
	OrderID       string `json:"order_id"`
	ClientOrderID string `json:"client_order_id"`
	Symbol        string `json:"symbol"`
	Status        string `json:"status"`
}

type CancelOrderRequest struct {
	ClientOrderID string `json:"client_order_id,omitempty"`
	OrderID       string `json:"order_id,omitempty"`
	AccountID     string `json:"account_id"`
}

type CancelOrderResponse struct {
	Success bool   `json:"success"`
	OrderID string `json:"order_id"`
	Message string `json:"message,omitempty"`
}

// SubmitSandboxOrder submits an order to the Webull OpenAPI sandbox.
func SubmitSandboxOrder(ctx context.Context, client *Client, accountID string, env Environment, order *models.OrderIntent) (*broker.BrokerOrder, error) {
	if env == EnvLive {
		return nil, ErrLiveTradingNotPermitted
	}
	if client == nil {
		return nil, broker.ErrBrokerNotConfigured
	}
	if order == nil {
		return nil, errors.New("order intent cannot be nil")
	}
	if order.ClientOrderID == "" {
		return nil, errors.New("client_order_id cannot be empty")
	}

	side := "BUY"
	if order.Side == models.SideSell {
		side = "SELL"
	}

	orderType := "LIMIT"
	limitPrice := ""
	if order.ReferencePrice > 0 {
		limitPrice = fmt.Sprintf("%.2f", order.ReferencePrice)
	} else {
		orderType = "MARKET"
	}

	qtyStr := strconv.Itoa(order.Qty)
	if order.RequestedQty > 0 {
		qtyStr = fmt.Sprintf("%.0f", order.RequestedQty)
	}

	reqPayload := PlaceOrderRequest{
		ClientOrderID: order.ClientOrderID,
		AccountID:     accountID,
		Symbol:        order.Symbol,
		Side:          side,
		OrderType:     orderType,
		Quantity:      qtyStr,
		LimitPrice:    limitPrice,
		TimeInForce:   "DAY",
	}

	body, err := json.Marshal(reqPayload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal order request: %w", err)
	}

	code, respBody, err := client.ExecuteNoRetry(ctx, "POST", EndpointOrderPlace, nil, body)
	if err != nil {
		return nil, fmt.Errorf("failed to submit sandbox order (HTTP %d): %w", code, err)
	}

	var rawResp PlaceOrderResponse
	if err := json.Unmarshal(respBody, &rawResp); err != nil {
		return nil, fmt.Errorf("failed to unmarshal place order response: %w", err)
	}

	orderID := rawResp.OrderID
	if orderID == "" {
		orderID = rawResp.ClientOrderID
	}

	normStatus := broker.NormalizeBrokerStatus(rawResp.Status)
	now := time.Now().UTC()

	return &broker.BrokerOrder{
		ID:            orderID,
		BrokerOrderID: rawResp.OrderID,
		ClientOrderID: order.ClientOrderID,
		Symbol:        order.Symbol,
		Side:          string(order.Side),
		Qty:           order.Qty,
		RequestedQty:  order.RequestedQty,
		LimitPrice:    order.ReferencePrice,
		Status:        normStatus,
		RawStatus:     rawResp.Status,
		CreatedAt:     now,
		UpdatedAt:     now,
	}, nil
}

// CancelSandboxOrder dispatches a cancellation request to the Webull OpenAPI sandbox.
func CancelSandboxOrder(ctx context.Context, client *Client, accountID string, env Environment, clientOrderID string) error {
	if env == EnvLive {
		return ErrLiveTradingNotPermitted
	}
	if client == nil {
		return broker.ErrBrokerNotConfigured
	}
	if clientOrderID == "" {
		return errors.New("client_order_id cannot be empty")
	}

	reqPayload := CancelOrderRequest{
		ClientOrderID: clientOrderID,
		AccountID:     accountID,
	}

	body, err := json.Marshal(reqPayload)
	if err != nil {
		return fmt.Errorf("failed to marshal cancel request: %w", err)
	}

	code, respBody, err := client.ExecuteNoRetry(ctx, "POST", EndpointOrderCancel, nil, body)
	if err != nil {
		return fmt.Errorf("failed to cancel sandbox order (HTTP %d): %w", code, err)
	}

	var rawResp CancelOrderResponse
	if err := json.Unmarshal(respBody, &rawResp); err != nil {
		return fmt.Errorf("failed to unmarshal cancel order response: %w", err)
	}

	return nil
}

// QuerySandboxOrder queries a specific order by client_order_id or broker_order_id.
func QuerySandboxOrder(ctx context.Context, client *Client, accountID string, clientOrderID string) (*broker.BrokerOrder, error) {
	if client == nil {
		return nil, broker.ErrBrokerNotConfigured
	}

	orders, err := FetchOrders(ctx, client, accountID)
	if err != nil {
		return nil, err
	}

	for _, o := range orders {
		if o.ClientOrderID == clientOrderID || o.BrokerOrderID == clientOrderID {
			return &o, nil
		}
	}

	return nil, broker.ErrOrderNotFound
}
