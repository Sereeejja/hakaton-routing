package planning

import (
	"encoding/json"

	"github.com/google/uuid"
)

type RunDTO struct {
	RequestIDs       []uuid.UUID `json:"request_ids,omitempty"`
	BrigadeIDs       []uuid.UUID `json:"brigade_ids,omitempty"`
	SolverName       string      `json:"solver_name,omitempty" example:"ortools"`
	TimeLimitSeconds float64     `json:"time_limit_seconds,omitempty" example:"10"`
	Seed             int         `json:"seed,omitempty" example:"42"`
	SourcePlanID     *uuid.UUID  `json:"source_plan_id,omitempty"`
}

type SolverInput struct {
	ProblemID           string            `json:"problem_id"`
	Locations           []Location        `json:"locations"`
	Jobs                []Job             `json:"jobs"`
	Engineers           []Engineer        `json:"engineers"`
	PreviousAssignments map[string]string `json:"previous_assignments,omitempty"`
	Options             SolverOptions     `json:"options"`
}

type Location struct {
	ID        string  `json:"id"`
	Address   string  `json:"address"`
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
}

type Job struct {
	ID                string  `json:"id"`
	LocationID        string  `json:"location_id"`
	ServiceMinutes    int     `json:"service_minutes"`
	WindowStart       string  `json:"window_start"`
	WindowEnd         string  `json:"window_end"`
	RequiredSkill     string  `json:"required_skill"`
	RequiredTransport *string `json:"required_transport"`
	Priority          string  `json:"priority"`
}

type Engineer struct {
	ID              string   `json:"id"`
	StartLocationID string   `json:"start_location_id"`
	ShiftStart      string   `json:"shift_start"`
	ShiftEnd        string   `json:"shift_end"`
	Skills          []string `json:"skills"`
	Transport       string   `json:"transport"`
}

type SolverOptions struct {
	SolverName       string  `json:"solver"`
	TimeLimitSeconds float64 `json:"time_limit_sec"`
	Seed             int     `json:"seed"`
	TravelSpeedKMH   float64 `json:"travel_speed_kmh"`
	RoutingBaseURL   string  `json:"routing_base_url,omitempty"`
}

type Result struct {
	SolverName   string            `json:"solver_name"`
	Status       string            `json:"status"`
	Routes       []Route           `json:"routes"`
	Unassigned   []Unassigned      `json:"unassigned"`
	Metrics      Metrics           `json:"metrics"`
	Seed         int               `json:"seed"`
	Warnings     []string          `json:"warnings"`
	Metadata     json.RawMessage   `json:"metadata" swaggertype:"object"`
	Explanations map[string]string `json:"explanations"`
	Baseline     *Baseline         `json:"baseline,omitempty"`
}

type Baseline struct {
	SolverName string  `json:"solver_name"`
	Metrics    Metrics `json:"metrics"`
}

type Route struct {
	EngineerID          string          `json:"engineer_id"`
	DepartureMinutes    int             `json:"departure_minutes"`
	FinishMinutes       int             `json:"finish_minutes"`
	Stops               []Stop          `json:"stops"`
	TotalTravelMinutes  int             `json:"total_travel_minutes"`
	TotalWaitingMinutes int             `json:"total_waiting_minutes"`
	TotalServiceMinutes int             `json:"total_service_minutes"`
	TotalDistanceKM     float64         `json:"total_distance_km"`
	Geometry            json.RawMessage `json:"geometry,omitempty" swaggertype:"object"`
}

type Stop struct {
	Sequence            int     `json:"sequence"`
	JobID               string  `json:"job_id"`
	FromLocationID      string  `json:"from_location_id"`
	TravelMinutes       int     `json:"travel_minutes"`
	DistanceKM          float64 `json:"distance_km"`
	ArrivalMinutes      int     `json:"arrival_minutes"`
	ServiceStartMinutes int     `json:"service_start_minutes"`
	ServiceEndMinutes   int     `json:"service_end_minutes"`
	WaitingMinutes      int     `json:"waiting_minutes"`
}

type Unassigned struct {
	JobID   string `json:"job_id"`
	Code    string `json:"code"`
	Message string `json:"message"`
}

type Metrics struct {
	CompletedJobs           int      `json:"completed_jobs"`
	UnassignedUrgentJobs    int      `json:"unassigned_urgent_jobs"`
	UnassignedJobs          int      `json:"unassigned_jobs"`
	ActiveEngineers         int      `json:"active_engineers"`
	TotalDistanceKM         float64  `json:"total_distance_km"`
	TotalTravelMinutes      int      `json:"total_travel_minutes"`
	TotalWaitingMinutes     int      `json:"total_waiting_minutes"`
	MaxRouteDurationMinutes int      `json:"max_route_duration_minutes"`
	WorkloadStddevMinutes   float64  `json:"workload_stddev_minutes"`
	RuntimeSeconds          float64  `json:"runtime_seconds"`
	ObjectiveValue          *float64 `json:"objective_value"`
}
