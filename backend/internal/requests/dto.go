package requests

import "encoding/json"

type CreateDTO struct {
	ExternalID        string          `json:"external_id,omitempty" example:"REQ-1042"`
	Address           string          `json:"address" example:"Москва, ул. Тверская, 1"`
	Latitude          float64         `json:"latitude" example:"55.7578"`
	Longitude         float64         `json:"longitude" example:"37.6156"`
	ServiceMinutes    int             `json:"service_minutes" example:"70"`
	WindowStart       string          `json:"window_start" example:"10:00"`
	WindowEnd         string          `json:"window_end" example:"12:00"`
	RequiredSkill     string          `json:"required_skill" example:"connection"`
	RequiredTransport *string         `json:"required_transport,omitempty" example:"car"`
	Priority          string          `json:"priority,omitempty" example:"normal"`
	Metadata          json.RawMessage `json:"metadata,omitempty" swaggertype:"object"`
}

type UpdateStatusDTO struct {
	Status string `json:"status" enums:"pending,planned,completed,canceled"`
}

type DeleteAllResponse struct {
	DeletedCount int64 `json:"deleted_count" example:"12"`
}
