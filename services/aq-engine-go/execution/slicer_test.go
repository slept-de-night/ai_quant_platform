package execution

import "testing"

func TestVWAPPreservesQuantity(t *testing.T) {
	orders := SliceVWAP(
		1050,
		[]float64{
			0.10,
			0.20,
			0.40,
			0.20,
			0.10,
		},
	)
	if got := TotalQuantity(orders); got != 1050 {
		t.Fatalf(
			"expected total 1050, got %d",
			got,
		)
	}
}

func TestTWAPPreservesQuantity(t *testing.T) {
	orders := SliceTWAP(
		12345,
		1800,
		12,
		0.10,
	)
	if got := TotalQuantity(orders); got != 12345 {
		t.Fatalf(
			"expected total 12345, got %d",
			got,
		)
	}
}
