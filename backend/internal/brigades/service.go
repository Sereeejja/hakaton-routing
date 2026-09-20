package brigades

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

var ErrValidation = errors.New("brigade validation failed")

type Service struct {
	repository Repository
}

func NewService(repository Repository) *Service {
	return &Service{repository: repository}
}

func (s *Service) Create(ctx context.Context, dto CreateDTO) (Brigade, error) {
	dto.Name = strings.TrimSpace(dto.Name)
	dto.StartAddress = strings.TrimSpace(dto.StartAddress)
	dto.Skills = unique(dto.Skills)
	if err := validateCreate(dto); err != nil {
		return Brigade{}, err
	}
	return s.repository.Create(ctx, dto)
}

func (s *Service) List(ctx context.Context) ([]Brigade, error) {
	return s.repository.List(ctx)
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (Brigade, error) {
	return s.repository.Get(ctx, id)
}

func (s *Service) UpdateStatus(ctx context.Context, id uuid.UUID, status string) (Brigade, error) {
	if status != "available" && status != "unavailable" {
		return Brigade{}, fmt.Errorf("%w: unknown status", ErrValidation)
	}
	return s.repository.UpdateStatus(ctx, id, status)
}

func validateCreate(dto CreateDTO) error {
	if dto.Name == "" || dto.StartAddress == "" {
		return fmt.Errorf("%w: name and start_address are required", ErrValidation)
	}
	if dto.StartLatitude < -90 || dto.StartLatitude > 90 || dto.StartLongitude < -180 || dto.StartLongitude > 180 {
		return fmt.Errorf("%w: invalid coordinates", ErrValidation)
	}
	start, err := time.Parse("15:04", dto.ShiftStart)
	if err != nil {
		return fmt.Errorf("%w: shift_start must be HH:MM", ErrValidation)
	}
	end, err := time.Parse("15:04", dto.ShiftEnd)
	if err != nil || start.After(end) {
		return fmt.Errorf("%w: invalid shift_end", ErrValidation)
	}
	if len(dto.Skills) == 0 {
		return fmt.Errorf("%w: at least one skill is required", ErrValidation)
	}
	for _, skill := range dto.Skills {
		if !contains(skill, "connection", "local", "emergency") {
			return fmt.Errorf("%w: unknown skill %q", ErrValidation, skill)
		}
	}
	if !contains(dto.Transport, "car", "walk", "bicycle", "public_transit") {
		return fmt.Errorf("%w: unknown transport", ErrValidation)
	}
	return nil
}

func unique(values []string) []string {
	seen := make(map[string]struct{}, len(values))
	result := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if _, ok := seen[value]; value == "" || ok {
			continue
		}
		seen[value] = struct{}{}
		result = append(result, value)
	}
	return result
}

func contains(value string, values ...string) bool {
	for _, candidate := range values {
		if value == candidate {
			return true
		}
	}
	return false
}
