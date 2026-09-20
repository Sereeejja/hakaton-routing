package replanning

import (
	"errors"
	"net/http"

	"github.com/Sereeejja/hakaton-routing/backend/internal/brigades"
	"github.com/Sereeejja/hakaton-routing/backend/internal/planning"
	"github.com/Sereeejja/hakaton-routing/backend/internal/plans"
	"github.com/Sereeejja/hakaton-routing/backend/internal/requests"
	"github.com/Sereeejja/hakaton-routing/backend/internal/web"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type Handler struct {
	service *Service
}

func NewHandler(service *Service) *Handler {
	return &Handler{service: service}
}

// Apply godoc
// @Summary Применить событие и перестроить план
// @Tags replanning
// @Accept json
// @Produce json
// @Param id path string true "UUID исходного плана"
// @Param event body EventDTO true "Событие"
// @Success 201 {object} Result
// @Failure 422 {object} web.ErrorResponse
// @Router /plans/{id}/events [post]
func (h *Handler) Apply(w http.ResponseWriter, r *http.Request) {
	planID, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		web.Error(w, http.StatusBadRequest, "invalid_id", "id must be UUID")
		return
	}
	var dto EventDTO
	if !web.DecodeJSON(w, r, &dto) {
		return
	}
	result, err := h.service.Apply(r.Context(), planID, dto)
	if err != nil {
		switch {
		case errors.Is(err, ErrValidation), errors.Is(err, planning.ErrValidation),
			errors.Is(err, requests.ErrValidation), errors.Is(err, brigades.ErrValidation):
			web.Error(w, http.StatusUnprocessableEntity, "validation_error", err.Error())
		case errors.Is(err, plans.ErrNotFound), errors.Is(err, requests.ErrNotFound),
			errors.Is(err, brigades.ErrNotFound):
			web.Error(w, http.StatusNotFound, "not_found", err.Error())
		default:
			web.Error(w, http.StatusServiceUnavailable, "replanning_failed", err.Error())
		}
		return
	}
	web.JSON(w, http.StatusCreated, result)
}
