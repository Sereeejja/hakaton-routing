package replanning

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/Sereeejja/hakaton-routing/backend/internal/brigades"
	"github.com/Sereeejja/hakaton-routing/backend/internal/planning"
	"github.com/Sereeejja/hakaton-routing/backend/internal/plans"
	"github.com/Sereeejja/hakaton-routing/backend/internal/requests"
	"github.com/google/uuid"
)

var ErrValidation = errors.New("replanning validation failed")

type EventDTO struct {
	Type    string          `json:"type" example:"cancel_request"`
	Payload json.RawMessage `json:"payload" swaggertype:"object"`
}

type Result struct {
	Event plans.ReplanEvent `json:"event"`
	Plan  plans.Plan        `json:"plan"`
}

type Service struct {
	plans    plans.Repository
	requests *requests.Service
	brigades *brigades.Service
	planning *planning.Service
}

func NewService(
	planRepository plans.Repository,
	requestService *requests.Service,
	brigadeService *brigades.Service,
	planningService *planning.Service,
) *Service {
	return &Service{
		plans: planRepository, requests: requestService,
		brigades: brigadeService, planning: planningService,
	}
}

func (s *Service) Apply(ctx context.Context, planID uuid.UUID, dto EventDTO) (Result, error) {
	basePlan, err := s.plans.Get(ctx, planID)
	if err != nil {
		return Result{}, err
	}
	if !eventTypeAllowed(dto.Type) || len(dto.Payload) == 0 {
		return Result{}, fmt.Errorf("%w: unknown event or empty payload", ErrValidation)
	}
	event, err := s.plans.CreateEvent(ctx, planID, dto.Type, dto.Payload)
	if err != nil {
		return Result{}, err
	}
	if err = s.applyMutation(ctx, dto); err != nil {
		_ = s.plans.FailEvent(ctx, event.ID, err.Error())
		return Result{}, err
	}
	newPlan, err := s.planning.Run(ctx, planning.RunDTO{
		SolverName: basePlan.SolverName, TimeLimitSeconds: basePlan.TimeLimitSeconds,
		Seed: basePlan.Seed, SourcePlanID: &basePlan.ID,
	})
	if err != nil {
		_ = s.plans.FailEvent(ctx, event.ID, err.Error())
		return Result{}, err
	}
	if err = s.plans.CompleteEvent(ctx, event.ID, newPlan.ID); err != nil {
		return Result{}, err
	}
	now := time.Now().UTC()
	event.Status = "applied"
	event.ResultingPlanID = &newPlan.ID
	event.ProcessedAt = &now
	return Result{Event: event, Plan: newPlan}, nil
}

func (s *Service) applyMutation(ctx context.Context, dto EventDTO) error {
	switch dto.Type {
	case "cancel_request":
		var payload struct {
			RequestID uuid.UUID `json:"request_id"`
		}
		if err := json.Unmarshal(dto.Payload, &payload); err != nil || payload.RequestID == uuid.Nil {
			return fmt.Errorf("%w: request_id is required", ErrValidation)
		}
		_, err := s.requests.UpdateStatus(ctx, payload.RequestID, "canceled")
		return err
	case "brigade_unavailable":
		var payload struct {
			BrigadeID uuid.UUID `json:"brigade_id"`
		}
		if err := json.Unmarshal(dto.Payload, &payload); err != nil || payload.BrigadeID == uuid.Nil {
			return fmt.Errorf("%w: brigade_id is required", ErrValidation)
		}
		_, err := s.brigades.UpdateStatus(ctx, payload.BrigadeID, "unavailable")
		return err
	case "new_urgent_request":
		var payload requests.CreateDTO
		if err := json.Unmarshal(dto.Payload, &payload); err != nil {
			return fmt.Errorf("%w: invalid request payload", ErrValidation)
		}
		payload.Priority = "urgent"
		_, err := s.requests.Create(ctx, payload)
		return err
	default:
		return fmt.Errorf("%w: unknown event type", ErrValidation)
	}
}

func eventTypeAllowed(value string) bool {
	return value == "cancel_request" || value == "brigade_unavailable" || value == "new_urgent_request"
}
