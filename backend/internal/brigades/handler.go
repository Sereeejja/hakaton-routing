package brigades

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
	router.Post("/", h.Create)
	router.Get("/{id}", h.Get)
	router.Patch("/{id}/status", h.UpdateStatus)
	return router
}

// Create godoc
// @Summary Создать бригаду
// @Tags brigades
// @Accept json
// @Produce json
// @Param brigade body CreateDTO true "Бригада"
// @Success 201 {object} Brigade
// @Failure 400 {object} web.ErrorResponse
// @Router /brigades/ [post]
func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
	var dto CreateDTO
	if !web.DecodeJSON(w, r, &dto) {
		return
	}
	item, err := h.service.Create(r.Context(), dto)
	if err != nil {
		writeError(w, err)
		return
	}
	web.JSON(w, http.StatusCreated, item)
}

// List godoc
// @Summary Список бригад
// @Tags brigades
// @Produce json
// @Success 200 {array} Brigade
// @Router /brigades/ [get]
func (h *Handler) List(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.List(r.Context())
	if err != nil {
		writeError(w, err)
		return
	}
	web.JSON(w, http.StatusOK, items)
}

// Get godoc
// @Summary Получить бригаду
// @Tags brigades
// @Produce json
// @Param id path string true "UUID бригады"
// @Success 200 {object} Brigade
// @Failure 404 {object} web.ErrorResponse
// @Router /brigades/{id} [get]
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		web.Error(w, http.StatusBadRequest, "invalid_id", "id must be UUID")
		return
	}
	item, err := h.service.Get(r.Context(), id)
	if err != nil {
		writeError(w, err)
		return
	}
	web.JSON(w, http.StatusOK, item)
}

// UpdateStatus godoc
// @Summary Изменить доступность бригады
// @Tags brigades
// @Accept json
// @Produce json
// @Param id path string true "UUID бригады"
// @Param status body UpdateStatusDTO true "Новый статус"
// @Success 200 {object} Brigade
// @Router /brigades/{id}/status [patch]
func (h *Handler) UpdateStatus(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "id"))
	if err != nil {
		web.Error(w, http.StatusBadRequest, "invalid_id", "id must be UUID")
		return
	}
	var dto UpdateStatusDTO
	if !web.DecodeJSON(w, r, &dto) {
		return
	}
	item, err := h.service.UpdateStatus(r.Context(), id, dto.Status)
	if err != nil {
		writeError(w, err)
		return
	}
	web.JSON(w, http.StatusOK, item)
}

func writeError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, ErrValidation):
		web.Error(w, http.StatusUnprocessableEntity, "validation_error", err.Error())
	case errors.Is(err, ErrNotFound):
		web.Error(w, http.StatusNotFound, "not_found", err.Error())
	default:
		web.Error(w, http.StatusInternalServerError, "internal_error", err.Error())
	}
}
