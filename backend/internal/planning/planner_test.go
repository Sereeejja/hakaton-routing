package planning

import (
	"context"
	"os"
	"testing"
	"time"
)

func TestPythonPlannerContract(t *testing.T) {
	python := "../../../solver/.venv/bin/python"
	pythonPath := "../../../solver/src"
	if _, err := os.Stat(python); err != nil {
		t.Skip("solver virtual environment is not installed")
	}
	planner := NewPythonPlanner(python, pythonPath, 5*time.Second)
	result, err := planner.Solve(context.Background(), SolverInput{
		ProblemID: "backend-contract-test",
		Locations: []Location{
			{ID: "office", Address: "Office", Latitude: 55.75, Longitude: 37.61},
			{ID: "customer", Address: "Customer", Latitude: 55.76, Longitude: 37.62},
		},
		Jobs: []Job{{
			ID: "00000000-0000-0000-0000-000000000001", LocationID: "customer",
			ServiceMinutes: 30, WindowStart: "10:00", WindowEnd: "15:00",
			RequiredSkill: "local", Priority: "normal",
		}},
		Engineers: []Engineer{{
			ID: "00000000-0000-0000-0000-000000000002", StartLocationID: "office",
			ShiftStart: "09:00", ShiftEnd: "18:00", Skills: []string{"local"}, Transport: "car",
		}},
		Options: SolverOptions{SolverName: "greedy", TimeLimitSeconds: 1, Seed: 42, TravelSpeedKMH: 30},
	})
	if err != nil {
		t.Fatalf("Solve() error = %v", err)
	}
	if result.Status != "feasible" || len(result.Routes) != 1 || len(result.Routes[0].Stops) != 1 {
		t.Fatalf("unexpected result: %#v", result)
	}
}
