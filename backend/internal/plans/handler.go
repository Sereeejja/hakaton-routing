package plans

import (
	"errors"
	"net/http"

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

func (h *Handler) Routes() chi.Router {
	router := chi.NewRouter()
	router.Get("/", h.List)
	router.Get("/{id}", h.Get)
	return router
}

// List godoc
// @Summary Последние планы
// @Tags plans
// @Produce json
// @Success 200 {array} Plan
// @Router /plans/ [get]
func (h *Handler) List(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.List(r.Context())
	if err != nil {
		web.Error(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}
	web.JSON(w, http.StatusOK, items)
}

// Get godoc
// @Summary Получить план
// @Tags plans
// @Produce json
// @Param id path string true "UUID плана"
// @Success 200 {object} Plan
// @Failure 404 {object} web.ErrorResponse
// @Router /plans/{id} [get]
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		web.Error(w, http.StatusBadRequest, "invalid_id", "id must be UUID")
		return
	}
	item, err := h.service.Get(r.Context(), id)
	if errors.Is(err, ErrNotFound) {
		web.Error(w, http.StatusNotFound, "not_found", err.Error())
		return
	}
	if err != nil {
		web.Error(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}
	web.JSON(w, http.StatusOK, item)
}
