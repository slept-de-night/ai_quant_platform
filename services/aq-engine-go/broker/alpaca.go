package broker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"aq-engine-go/models"
)

type AlpacaPaperClient struct {
	apiKey    string
	secretKey string
	baseURL   string
	client    *http.Client
}

func NewAlpacaPaperClient(apiKey, secretKey string) *AlpacaPaperClient {
	return &AlpacaPaperClient{
		apiKey:    apiKey,
		secretKey: secretKey,
		baseURL:   "https://paper-api.alpaca.markets",
		client:    &http.Client{Timeout: 10 * time.Second},
	}
}

func (c *AlpacaPaperClient) IsConfigured() bool {
	return c.apiKey != "" && c.secretKey != ""
}

type alpacaOrderRequest struct {
	Symbol        string `json:"symbol"`
	Qty           int    `json:"qty"`
	Side          string `json:"side"`
	Type          string `json:"type"`
	TimeInForce   string `json:"time_in_force"`
	ClientOrderID string `json:"client_order_id"`
}

type alpacaOrderResponse struct {
	ID            string `json:"id"`
	ClientOrderID string `json:"client_order_id"`
	Status        string `json:"status"`
	Symbol        string `json:"symbol"`
	Qty           string `json:"qty"`
	Side          string `json:"side"`
}

func (c *AlpacaPaperClient) SubmitOrder(order *models.OrderIntent) (*alpacaOrderResponse, error) {
	if !c.IsConfigured() {
		// Mock paper execution if keys not set
		return &alpacaOrderResponse{
			ID:            fmt.Sprintf("mock-paper-%d", time.Now().UnixNano()),
			ClientOrderID: order.ClientOrderID,
			Status:        "accepted",
			Symbol:        order.Symbol,
			Qty:           strconv.Itoa(order.Qty),
			Side:          string(order.Side),
		}, nil
	}

	reqBody, err := json.Marshal(alpacaOrderRequest{
		Symbol:        order.Symbol,
		Qty:           order.Qty,
		Side:          string(order.Side),
		Type:          "market",
		TimeInForce:   "day",
		ClientOrderID: order.ClientOrderID,
	})
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", c.baseURL+"/v2/orders", bytes.NewBuffer(reqBody))
	if err != nil {
		return nil, err
	}

	req.Header.Set("APCA-API-KEY-ID", c.apiKey)
	req.Header.Set("APCA-API-SECRET-KEY", c.secretKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	bodyBytes, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("alpaca api error (%d): %s", resp.StatusCode, string(bodyBytes))
	}

	var res alpacaOrderResponse
	if err := json.Unmarshal(bodyBytes, &res); err != nil {
		return nil, err
	}

	return &res, nil
}
