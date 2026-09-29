package brigades

import "encoding/json"

type CreateDTO struct {
	Name           string          `json:"name" example:"Бригада Восток-1"`
	StartAddress   string          `json:"start_address" example:"Москва, Измайловское шоссе, 1"`
	StartLatitude  float64         `json:"start_latitude" example:"55.7891"`
	StartLongitude float64         `json:"start_longitude" example:"37.7488"`
	ShiftStart     string          `json:"shift_start" example:"10:00"`
	ShiftEnd       string          `json:"shift_end" example:"22:00"`
	WorkSchedule   string          `json:"work_schedule,omitempty" enums:"2/2,5/2" example:"2/2"`
	Skills         []string        `json:"skills" example:"connection,local"`
	Transport      string          `json:"transport" example:"car"`
	Metadata       json.RawMessage `json:"metadata,omitempty" swaggertype:"object"`
}

type UpdateStatusDTO struct {
	Status string `json:"status" enums:"available,unavailable"`
}
