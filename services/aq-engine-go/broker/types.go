package broker

import (
	"time"
)

type BrokerKind string

const (
	BrokerKindPaper  BrokerKind = "paper"
	BrokerKindWebull BrokerKind = "webull"
	BrokerKindAlpaca BrokerKind = "alpaca"
	BrokerKindIBKR   BrokerKind = "ibkr"
)

type Environment string

const (
	EnvSimulation Environment = "simulation"
	EnvPaper      Environment = "paper"
	EnvLive       Environment = "live"
)

type BrokerOrder struct {
	ID            string    `json:"id"`
	ClientOrderID string    `json:"client_order_id"`
	Symbol        string    `json:"symbol"`
	Side          string    `json:"side"`
	Qty           int       `json:"qty"`
	FilledQty     int       `json:"filled_qty"`
	Status        string    `json:"status"`
	LimitPrice    float64   `json:"limit_price,omitempty"`
	AvgPrice      float64   `json:"avg_price,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

type BrokerPosition struct {
	Symbol      string  `json:"symbol"`
	Qty         float64 `json:"qty"`
	MarketValue float64 `json:"market_value"`
	CostBasis   float64 `json:"cost_basis"`
}

type AccountState struct {
	Cash        float64 `json:"cash"`
	Equity      float64 `json:"equity"`
	BuyingPower float64 `json:"buying_power"`
	Currency    string  `json:"currency"`
}

type Health struct {
	Ready         bool        `json:"ready"`
	Connected     bool        `json:"connected"`
	Broker        BrokerKind  `json:"broker"`
	Name          string      `json:"name"`
	Environment   Environment `json:"environment"`
	Message       string      `json:"message"`
	LastCheckedAt time.Time   `json:"last_checked_at"`
}
