package execution

import (
	"math"
	rand "math/rand/v2"
	"sort"
	"time"
)

const DefaultRoundLot = 100

// ChildOrder describes one execution child slice.
type ChildOrder struct {
	Slice           int           `json:"slice"`
	Bucket          int           `json:"bucket"`
	Quantity        int           `json:"quantity"`
	TargetWeight    float64       `json:"target_weight"`
	ScheduledOffset time.Duration `json:"scheduled_offset"`
}

// SliceTWAP divides totalQty approximately equally across time with randomized timing jitter.
func SliceTWAP(
	totalQty int,
	totalDurationSec int,
	slices int,
	jitterPct float64,
) []ChildOrder {
	return sliceTWAPWithRandom(
		totalQty,
		totalDurationSec,
		slices,
		jitterPct,
		rand.Float64,
	)
}

func sliceTWAPWithRandom(
	totalQty int,
	totalDurationSec int,
	slices int,
	jitterPct float64,
	randomFloat func() float64,
) []ChildOrder {
	if totalQty <= 0 || totalDurationSec <= 0 || slices <= 0 || randomFloat == nil {
		return nil
	}
	if math.IsNaN(jitterPct) || math.IsInf(jitterPct, 0) {
		return nil
	}
	if jitterPct < 0 {
		jitterPct = 0
	}
	if jitterPct > 0.49 {
		jitterPct = 0.49
	}

	weights := make([]float64, slices)
	equalWeight := 1.0 / float64(slices)
	for i := range weights {
		weights[i] = equalWeight
	}

	quantities := allocateRoundLots(
		totalQty,
		weights,
		DefaultRoundLot,
		slices-1,
	)

	orders := make([]ChildOrder, slices)
	intervalSec := float64(totalDurationSec) / float64(slices)
	totalDuration := time.Duration(totalDurationSec) * time.Second

	for i := 0; i < slices; i++ {
		baseSec := float64(i) * intervalSec
		if i > 0 && jitterPct > 0 {
			randomValue := randomFloat()
			if randomValue < 0 {
				randomValue = 0
			}
			if randomValue >= 1 {
				randomValue = math.Nextafter(1.0, 0.0)
			}
			signedRandom := 2.0*randomValue - 1.0
			jitterSec := signedRandom * jitterPct * intervalSec
			baseSec += jitterSec
		}
		if baseSec < 0 {
			baseSec = 0
		}
		offset := time.Duration(baseSec * float64(time.Second))
		if offset >= totalDuration {
			offset = totalDuration - time.Nanosecond
			if offset < 0 {
				offset = 0
			}
		}
		orders[i] = ChildOrder{
			Slice:           i,
			Bucket:          i,
			Quantity:        quantities[i],
			TargetWeight:    equalWeight,
			ScheduledOffset: offset,
		}
	}
	return orders
}

// SliceVWAP allocates parent quantity according to an arbitrary volume profile using largest-remainder round lotting.
func SliceVWAP(
	totalQty int,
	volumeProfile []float64,
) []ChildOrder {
	if totalQty <= 0 || len(volumeProfile) == 0 {
		return nil
	}
	weights, ok := normalizeWeights(volumeProfile)
	if !ok {
		return nil
	}
	oddLotBucket := maxWeightIndex(weights)
	quantities := allocateRoundLots(
		totalQty,
		weights,
		DefaultRoundLot,
		oddLotBucket,
	)
	orders := make([]ChildOrder, len(weights))
	for i := range weights {
		orders[i] = ChildOrder{
			Slice:           i,
			Bucket:          i,
			Quantity:        quantities[i],
			TargetWeight:    weights[i],
			ScheduledOffset: 0,
		}
	}
	return orders
}

func normalizeWeights(values []float64) ([]float64, bool) {
	if len(values) == 0 {
		return nil, false
	}
	weights := make([]float64, len(values))
	total := 0.0
	for i, value := range values {
		if math.IsNaN(value) || math.IsInf(value, 0) || value < 0 {
			return nil, false
		}
		weights[i] = value
		total += value
	}
	if total <= 0 {
		return nil, false
	}
	for i := range weights {
		weights[i] /= total
	}
	return weights, true
}

type remainder struct {
	index    int
	fraction float64
}

func allocateRoundLots(
	totalQty int,
	weights []float64,
	lot int,
	oddLotIndex int,
) []int {
	n := len(weights)
	if totalQty <= 0 || n == 0 {
		return nil
	}
	if lot <= 0 {
		lot = 1
	}
	if oddLotIndex < 0 || oddLotIndex >= n {
		oddLotIndex = n - 1
	}
	result := make([]int, n)
	totalLots := totalQty / lot
	oddLotQty := totalQty % lot
	remainders := make([]remainder, n)
	allocatedLots := 0

	for i, weight := range weights {
		idealLots := float64(totalLots) * weight
		wholeLots := int(math.Floor(idealLots))
		result[i] = wholeLots * lot
		allocatedLots += wholeLots
		remainders[i] = remainder{
			index:    i,
			fraction: idealLots - float64(wholeLots),
		}
	}

	remainingLots := totalLots - allocatedLots
	sort.SliceStable(remainders, func(i, j int) bool {
		return remainders[i].fraction > remainders[j].fraction
	})

	for i := 0; i < remainingLots; i++ {
		index := remainders[i].index
		result[index] += lot
	}

	if oddLotQty > 0 {
		result[oddLotIndex] += oddLotQty
	}
	return result
}

func maxWeightIndex(weights []float64) int {
	if len(weights) == 0 {
		return -1
	}
	bestIndex := 0
	bestWeight := weights[0]
	for i := 1; i < len(weights); i++ {
		if weights[i] > bestWeight {
			bestIndex = i
			bestWeight = weights[i]
		}
	}
	return bestIndex
}

// TotalQuantity sums the quantities of all child orders.
func TotalQuantity(orders []ChildOrder) int {
	total := 0
	for _, order := range orders {
		total += order.Quantity
	}
	return total
}
