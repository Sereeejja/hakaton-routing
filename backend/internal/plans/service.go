package plans

import (
	"context"

	"github.com/google/uuid"
)

type Service struct {
	repository Repository
}

func NewService(repository Repository) *Service {
	return &Service{repository: repository}
}

func (s *Service) List(ctx context.Context) ([]Plan, error) {
	return s.repository.List(ctx)
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (Plan, error) {
	return s.repository.Get(ctx, id)
}
