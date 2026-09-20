package planning

import (
	"errors"
	"net/http"

	"github.com/Sereeejja/hakaton-routing/backend/internal/plans"
	"github.com/Sereeejja/hakaton-routing/backend/internal/web"
)

type PlanResponse = plans.Plan

type Handler struct {
	service *Service
}

func NewHandler(service *Service) *Handler {
	return &Handler{service: service}
}

// CreatePlan godoc
// @Summary Построить план маршрутов
// @Description Синхронно запускает solver для выбранных или всех активных сущностей
// @Tags planning
// @Accept json
// @Produce json
// @Param options body RunDTO true "Настройки расчёта"
// @Success 201 {object} PlanResponse
// @Failure 422 {object} web.ErrorResponse
// @Failure 503 {object} web.ErrorResponse
// @Router /plans/ [post]
func (h *Handler) CreatePlan(w http.ResponseWriter, r *http.Request) {
	var dto RunDTO
	if !web.DecodeJSON(w, r, &dto) {
		return
	}
	plan, err := h.service.Run(r.Context(), dto)
	if err != nil {
		if errors.Is(err, ErrValidation) {
			web.Error(w, http.StatusUnprocessableEntity, "validation_error", err.Error())
			return
		}
		web.Error(w, http.StatusServiceUnavailable, "planning_failed", err.Error())
		return
	}
	web.JSON(w, http.StatusCreated, plan)
}
