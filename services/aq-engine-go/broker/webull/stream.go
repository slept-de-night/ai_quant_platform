package webull

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"

	"aq-engine-go/broker"
	"aq-engine-go/models"
)

// StreamEventType defines execution event types from Webull gRPC streaming.
type StreamEventType string

const (
	EventTypeOrderStatus StreamEventType = "ORDER_STATUS"
	EventTypeOrderFill   StreamEventType = "ORDER_FILL"
	EventTypeHeartbeat   StreamEventType = "HEARTBEAT"
)

// StreamMessage represents a deserialized Webull streaming event.
type StreamMessage struct {
	Type          StreamEventType `json:"type"`
	AccountID     string          `json:"account_id"`
	OrderID       string          `json:"order_id"`
	ClientOrderID string          `json:"client_order_id"`
	Symbol        string          `json:"symbol"`
	Side          string          `json:"side"` // "BUY", "SELL"
	Status        string          `json:"status"`
	Quantity      float64         `json:"quantity"`
	FilledQty     float64         `json:"filled_qty"`
	Price         float64         `json:"price"`
	FillID        string          `json:"fill_id"`
	Timestamp     time.Time       `json:"timestamp"`
}

// OMSConsumer abstracts OMS engine fill and status update methods.
type OMSConsumer interface {
	ApplyFill(fill models.Fill) (*models.Position, error)
	UpdateOrderStatus(clientOrderID string, status models.OrderStatus, reasons ...string) error
}

// StreamSource abstracts the underlying gRPC stream connection.
type StreamSource interface {
	Receive(ctx context.Context) (*StreamMessage, error)
	Close() error
}

// FallbackPoller callback when stream is disconnected or silent.
type FallbackPoller func(ctx context.Context) error

// StreamConsumer manages streaming event processing, reconnection, and fallback polling.
type StreamConsumer struct {
	mu                     sync.Mutex
	oms                    OMSConsumer
	fallbackPoller         FallbackPoller
	running                bool
	connected              bool
	lastHeartbeat          time.Time
	fallbackTimeout        time.Duration
	initialBackoff         time.Duration
	maxBackoff             time.Duration
	cancelFunc             context.CancelFunc
	fallbackTriggerCount   int
	eventsProcessedCounter int
}

// NewStreamConsumer creates a Webull execution event stream consumer.
func NewStreamConsumer(oms OMSConsumer, fallbackPoller FallbackPoller, fallbackTimeout time.Duration) *StreamConsumer {
	if fallbackTimeout <= 0 {
		fallbackTimeout = 30 * time.Second
	}
	return &StreamConsumer{
		oms:             oms,
		fallbackPoller:  fallbackPoller,
		fallbackTimeout: fallbackTimeout,
		initialBackoff:  100 * time.Millisecond,
		maxBackoff:      5 * time.Second,
		lastHeartbeat:   time.Now().UTC(),
	}
}

// IsRunning reports whether the streaming consumer goroutine is active.
func (sc *StreamConsumer) IsRunning() bool {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	return sc.running
}

// IsConnected reports whether the consumer currently has an active streaming connection.
func (sc *StreamConsumer) IsConnected() bool {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	return sc.connected
}

// FallbackTriggerCount returns number of times fallback polling was triggered due to silence/disconnection.
func (sc *StreamConsumer) FallbackTriggerCount() int {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	return sc.fallbackTriggerCount
}

// ProcessMessage processes a raw streaming message and dispatches it to OMS.
func (sc *StreamConsumer) ProcessMessage(msg *StreamMessage) error {
	if msg == nil {
		return errors.New("stream message cannot be nil")
	}

	sc.mu.Lock()
	sc.lastHeartbeat = time.Now().UTC()
	sc.eventsProcessedCounter++
	sc.mu.Unlock()

	switch msg.Type {
	case EventTypeHeartbeat:
		return nil

	case EventTypeOrderStatus:
		if sc.oms == nil {
			return nil
		}
		normStatus := broker.NormalizeBrokerStatus(msg.Status)
		cID := msg.ClientOrderID
		if cID == "" {
			cID = msg.OrderID
		}
		var omsStatus models.OrderStatus
		switch normStatus {
		case broker.BrokerOrderStatusAcknowledged:
			omsStatus = models.OrderStatusAcknowledged
		case broker.BrokerOrderStatusPartiallyFilled:
			omsStatus = models.OrderStatusPartiallyFilled
		case broker.BrokerOrderStatusFilled:
			omsStatus = models.OrderStatusFilled
		case broker.BrokerOrderStatusCanceled:
			omsStatus = models.OrderStatusCancelled
		case broker.BrokerOrderStatusSubmitFailed, broker.BrokerOrderStatusRejected:
			omsStatus = models.OrderStatusSubmitFailed
		default:
			omsStatus = models.OrderStatusAcknowledged
		}
		return sc.oms.UpdateOrderStatus(cID, omsStatus, msg.Status)

	case EventTypeOrderFill:
		if sc.oms == nil {
			return nil
		}
		fillID := msg.FillID
		if fillID == "" {
			fillID = fmt.Sprintf("wb-fill-%s-%d", msg.OrderID, time.Now().UnixNano())
		}
		side := models.SideBuy
		if msg.Side == "SELL" || msg.Side == "sell" {
			side = models.SideSell
		}
		ts := msg.Timestamp
		if ts.IsZero() {
			ts = time.Now().UTC()
		}

		fill := models.Fill{
			FillID:        fillID,
			ClientOrderID: msg.ClientOrderID,
			BrokerOrderID: msg.OrderID,
			Symbol:        msg.Symbol,
			Side:          side,
			Qty:           msg.Quantity,
			Price:         msg.Price,
			Timestamp:     ts,
		}
		_, err := sc.oms.ApplyFill(fill)
		return err

	default:
		return fmt.Errorf("unknown stream event type: %s", msg.Type)
	}
}

// Start launches the background streaming reader and disconnect watchdog.
func (sc *StreamConsumer) Start(ctx context.Context, sourceFactory func() (StreamSource, error)) {
	sc.mu.Lock()
	if sc.running {
		sc.mu.Unlock()
		return
	}
	consumerCtx, cancel := context.WithCancel(ctx)
	sc.cancelFunc = cancel
	sc.running = true
	sc.lastHeartbeat = time.Now().UTC()
	sc.mu.Unlock()

	go sc.runLoop(consumerCtx, sourceFactory)
}

// Stop terminates the streaming consumer and disconnect watchdog.
func (sc *StreamConsumer) Stop() {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	if sc.running && sc.cancelFunc != nil {
		sc.cancelFunc()
		sc.running = false
		sc.connected = false
	}
}

func (sc *StreamConsumer) runLoop(ctx context.Context, sourceFactory func() (StreamSource, error)) {
	watchdogTicker := time.NewTicker(1 * time.Second)
	defer watchdogTicker.Stop()

	backoff := sc.initialBackoff

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		source, err := sourceFactory()
		if err != nil {
			log.Printf("[WEBULL STREAM] Failed to establish gRPC stream: %v (retrying in %v)", err, backoff)
			sc.mu.Lock()
			sc.connected = false
			sc.mu.Unlock()

			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}
			backoff *= 2
			if backoff > sc.maxBackoff {
				backoff = sc.maxBackoff
			}
			continue
		}

		sc.mu.Lock()
		sc.connected = true
		sc.lastHeartbeat = time.Now().UTC()
		backoff = sc.initialBackoff
		sc.mu.Unlock()

		// Read loop from source
		for {
			select {
			case <-ctx.Done():
				source.Close()
				return
			case <-watchdogTicker.C:
				sc.checkWatchdog(ctx)
			default:
			}

			msg, err := source.Receive(ctx)
			if err != nil {
				log.Printf("[WEBULL STREAM] Stream disconnected: %v", err)
				source.Close()
				sc.mu.Lock()
				sc.connected = false
				sc.mu.Unlock()
				break
			}

			if err := sc.ProcessMessage(msg); err != nil {
				log.Printf("[WEBULL STREAM] Failed to process message: %v", err)
			}
		}
	}
}

func (sc *StreamConsumer) checkWatchdog(ctx context.Context) {
	sc.mu.Lock()
	silenceDuration := time.Since(sc.lastHeartbeat)
	shouldTriggerFallback := silenceDuration > sc.fallbackTimeout
	if shouldTriggerFallback {
		sc.fallbackTriggerCount++
		sc.lastHeartbeat = time.Now().UTC() // reset to avoid hammering
	}
	poller := sc.fallbackPoller
	sc.mu.Unlock()

	if shouldTriggerFallback && poller != nil {
		log.Printf("[WEBULL STREAM WATCHDOG] Stream silent for >%v. Triggering fallback polling.", silenceDuration)
		_ = poller(ctx)
	}
}

// ParseStreamPayload unmarshals raw JSON bytes into StreamMessage.
func ParseStreamPayload(data []byte) (*StreamMessage, error) {
	var msg StreamMessage
	if err := json.Unmarshal(data, &msg); err != nil {
		return nil, fmt.Errorf("failed to parse stream JSON: %w", err)
	}
	return &msg, nil
}
