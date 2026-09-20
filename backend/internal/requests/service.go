package requests

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

var ErrValidation = errors.New("request validation failed")

type Service struct {
	repository Repository
}

func NewService(repository Repository) *Service {
	return &Service{repository: repository}
}

func (s *Service) Create(ctx context.Context, dto CreateDTO) (Request, error) {
	dto.Address = strings.TrimSpace(dto.Address)
	if dto.Priority == "" {
		dto.Priority = "normal"
	}
	if err := validateCreate(dto); err != nil {
		return Request{}, err
	}
	return s.repository.Create(ctx, dto)
}

func (s *Service) List(ctx context.Context) ([]Request, error) {
	return s.repository.List(ctx)
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (Request, error) {
	return s.repository.Get(ctx, id)
}

func (s *Service) UpdateStatus(ctx context.Context, id uuid.UUID, status string) (Request, error) {
	if !oneOf(status, "pending", "planned", "completed", "canceled") {
		return Request{}, fmt.Errorf("%w: unknown status", ErrValidation)
	}
	return s.repository.UpdateStatus(ctx, id, status)
}

func validateCreate(dto CreateDTO) error {
	if dto.Address == "" {
		return fmt.Errorf("%w: address is required", ErrValidation)
	}
	if dto.Latitude < -90 || dto.Latitude > 90 || dto.Longitude < -180 || dto.Longitude > 180 {
		return fmt.Errorf("%w: invalid coordinates", ErrValidation)
	}
	if dto.ServiceMinutes <= 0 {
		return fmt.Errorf("%w: service_minutes must be positive", ErrValidation)
	}
	start, err := time.Parse("15:04", dto.WindowStart)
	if err != nil {
		return fmt.Errorf("%w: window_start must be HH:MM", ErrValidation)
	}
	end, err := time.Parse("15:04", dto.WindowEnd)
	if err != nil || start.After(end) {
		return fmt.Errorf("%w: invalid window_end", ErrValidation)
	}
	if !oneOf(dto.RequiredSkill, "connection", "local", "emergency") {
		return fmt.Errorf("%w: unknown required_skill", ErrValidation)
	}
	if dto.RequiredTransport != nil && !oneOf(*dto.RequiredTransport, "car", "walk", "bicycle", "public_transit") {
		return fmt.Errorf("%w: unknown required_transport", ErrValidation)
	}
	if !oneOf(dto.Priority, "normal", "urgent") {
		return fmt.Errorf("%w: unknown priority", ErrValidation)
	}
	return nil
}

func oneOf(value string, values ...string) bool {
	for _, candidate := range values {
		if value == candidate {
			return true
		}
	}
	return false
}
