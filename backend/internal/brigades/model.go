package brigades

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type Brigade struct {
	ID             uuid.UUID       `json:"id"`
	Name           string          `json:"name"`
	StartAddress   string          `json:"start_address"`
	StartLatitude  float64         `json:"start_latitude"`
	StartLongitude float64         `json:"start_longitude"`
	ShiftStart     string          `json:"shift_start" example:"10:00"`
	ShiftEnd       string          `json:"shift_end" example:"22:00"`
	WorkSchedule   string          `json:"work_schedule" enums:"2/2,5/2" example:"2/2"`
	Skills         []string        `json:"skills"`
	Transport      string          `json:"transport" enums:"car,walk,bicycle,public_transit"`
	Status         string          `json:"status" enums:"available,unavailable"`
	Metadata       json.RawMessage `json:"metadata" swaggertype:"object"`
	CreatedAt      time.Time       `json:"created_at"`
	UpdatedAt      time.Time       `json:"updated_at"`
}
