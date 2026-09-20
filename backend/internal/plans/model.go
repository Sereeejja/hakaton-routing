package plans

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type Plan struct {
	ID               uuid.UUID       `json:"id"`
	SourcePlanID     *uuid.UUID      `json:"source_plan_id,omitempty"`
	Status           string          `json:"status" enums:"running,feasible,partial,infeasible,error"`
	SolverName       string          `json:"solver_name"`
	Seed             int             `json:"seed"`
	TimeLimitSeconds float64         `json:"time_limit_seconds"`
	Solution         json.RawMessage `json:"solution,omitempty" swaggertype:"object"`
	ErrorMessage     *string         `json:"error_message,omitempty"`
	CreatedAt        time.Time       `json:"created_at"`
	CompletedAt      *time.Time      `json:"completed_at,omitempty"`
}

type CreateParams struct {
	SourcePlanID     *uuid.UUID
	SolverName       string
	Seed             int
	TimeLimitSeconds float64
}

type ReplanEvent struct {
	ID              uuid.UUID       `json:"id"`
	PlanID          uuid.UUID       `json:"plan_id"`
	ResultingPlanID *uuid.UUID      `json:"resulting_plan_id,omitempty"`
	Type            string          `json:"type"`
	Payload         json.RawMessage `json:"payload" swaggertype:"object"`
	Status          string          `json:"status"`
	ErrorMessage    *string         `json:"error_message,omitempty"`
	CreatedAt       time.Time       `json:"created_at"`
	ProcessedAt     *time.Time      `json:"processed_at,omitempty"`
}
