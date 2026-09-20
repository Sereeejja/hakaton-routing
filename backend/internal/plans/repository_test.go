package plans

import (
	"testing"
	"time"

	"github.com/google/uuid"
)

type nullSolutionScanner struct{}

func (nullSolutionScanner) Scan(dest ...any) error {
	*(dest[0].(*uuid.UUID)) = uuid.New()
	*(dest[1].(**uuid.UUID)) = nil
	*(dest[2].(*string)) = "running"
	*(dest[3].(*string)) = "greedy"
	*(dest[4].(*int)) = 42
	*(dest[5].(*float64)) = 2
	*(dest[6].(*[]byte)) = nil
	*(dest[7].(**string)) = nil
	*(dest[8].(*time.Time)) = time.Now()
	*(dest[9].(**time.Time)) = nil
	return nil
}

func TestScanPlanAcceptsNullSolutionForRunningPlan(t *testing.T) {
	plan, err := scanPlan(nullSolutionScanner{})
	if err != nil {
		t.Fatalf("scanPlan() error = %v", err)
	}
	if plan.Status != "running" || plan.Solution != nil {
		t.Fatalf("unexpected plan: %#v", plan)
	}
}
