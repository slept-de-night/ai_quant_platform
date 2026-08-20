package broker

import (
	"aq-engine-go/models"
	"aq-engine-go/reconciliation"
)

// BrokerAdapter defines the pluggable venue execution and reconciliation interface.
type BrokerAdapter interface {
	Name() string
	Kind() BrokerKind
	Environment() Environment
	IsConfigured() bool

	SubmitOrder(order *models.OrderIntent) (*BrokerOrder, error)
	CancelOrder(clientOrderID string) error
	GetOrder(clientOrderID string) (*BrokerOrder, error)
	ListOrders() ([]BrokerOrder, error)
	ListPositions() ([]BrokerPosition, error)
	GetAccountState() (*AccountState, error)
	GetHealth() Health
	GetBrokerSnapshot() (*reconciliation.BrokerState, error)
}
