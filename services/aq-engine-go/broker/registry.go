package broker

import (
	"fmt"
	"sync"
)

type Registry struct {
	mu            sync.RWMutex
	adapters      map[string]BrokerAdapter
	activeAdapter string
}

func NewRegistry() *Registry {
	return &Registry{
		adapters: make(map[string]BrokerAdapter),
	}
}

func (r *Registry) Register(adapter BrokerAdapter) {
	r.mu.Lock()
	defer r.mu.Unlock()

	name := adapter.Name()
	r.adapters[name] = adapter
	if r.activeAdapter == "" {
		r.activeAdapter = name
	}
}

func (r *Registry) SetActive(name string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.adapters[name]; !exists {
		return fmt.Errorf("broker adapter not found: %s", name)
	}
	r.activeAdapter = name
	return nil
}

func (r *Registry) GetActive() (BrokerAdapter, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if r.activeAdapter == "" {
		return nil, fmt.Errorf("no active broker adapter configured")
	}
	adapter, exists := r.adapters[r.activeAdapter]
	if !exists {
		return nil, fmt.Errorf("active broker adapter %s missing from registry", r.activeAdapter)
	}
	return adapter, nil
}

func (r *Registry) Get(name string) (BrokerAdapter, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	adapter, exists := r.adapters[name]
	if !exists {
		return nil, fmt.Errorf("broker adapter not found: %s", name)
	}
	return adapter, nil
}

func (r *Registry) List() []Health {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var list []Health
	for _, a := range r.adapters {
		list = append(list, a.GetHealth())
	}
	return list
}

type BrokerHealthResponse struct {
	ActiveBroker         string      `json:"active_broker"`
	Environment          Environment `json:"environment"`
	Ready                bool        `json:"ready"`
	Connected            bool        `json:"connected"`
	Message              string      `json:"message"`
	AllRegisteredBrokers []Health    `json:"all_registered_brokers"`
}

func (r *Registry) GetHealthSummary() (BrokerHealthResponse, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	active, err := r.GetActive()
	if err != nil {
		return BrokerHealthResponse{
			AllRegisteredBrokers: r.List(),
		}, err
	}

	h := active.GetHealth()
	return BrokerHealthResponse{
		ActiveBroker:         active.Name(),
		Environment:          active.Environment(),
		Ready:                h.Ready,
		Connected:            h.Connected,
		Message:              h.Message,
		AllRegisteredBrokers: r.List(),
	}, nil
}

