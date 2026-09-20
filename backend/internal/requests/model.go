package requests

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type Request struct {
	ID                uuid.UUID       `json:"id"`
	ExternalID        *string         `json:"external_id,omitempty"`
	Address           string          `json:"address"`
	Latitude          float64         `json:"latitude"`
	Longitude         float64         `json:"longitude"`
	ServiceMinutes    int             `json:"service_minutes"`
	WindowStart       string          `json:"window_start" example:"10:00"`
	WindowEnd         string          `json:"window_end" example:"12:00"`
	RequiredSkill     string          `json:"required_skill" enums:"connection,local,emergency"`
	RequiredTransport *string         `json:"required_transport,omitempty" enums:"car,walk,bicycle,public_transit"`
	Priority          string          `json:"priority" enums:"normal,urgent"`
	Status            string          `json:"status" enums:"pending,planned,completed,canceled"`
	Metadata          json.RawMessage `json:"metadata" swaggertype:"object"`
	CreatedAt         time.Time       `json:"created_at"`
	UpdatedAt         time.Time       `json:"updated_at"`
}
