package plans

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/google/uuid"
)

var ErrNotFound = errors.New("plan not found")

type Repository interface {
	Create(context.Context, CreateParams) (Plan, error)
	Complete(context.Context, uuid.UUID, json.RawMessage) (Plan, error)
	Fail(context.Context, uuid.UUID, string) (Plan, error)
	Get(context.Context, uuid.UUID) (Plan, error)
	List(context.Context) ([]Plan, error)
	CreateEvent(context.Context, uuid.UUID, string, json.RawMessage) (ReplanEvent, error)
	CompleteEvent(context.Context, uuid.UUID, uuid.UUID) error
	FailEvent(context.Context, uuid.UUID, string) error
}

type PostgresRepository struct {
	db *sql.DB
}

func NewPostgresRepository(db *sql.DB) *PostgresRepository {
	return &PostgresRepository{db: db}
}

const planColumns = `id, source_plan_id, status, solver_name, seed, time_limit_seconds,
	solution, error_message, created_at, completed_at`

func scanPlan(scanner interface{ Scan(...any) error }) (Plan, error) {
	var plan Plan
	var solution []byte
	err := scanner.Scan(
		&plan.ID, &plan.SourcePlanID, &plan.Status, &plan.SolverName, &plan.Seed,
		&plan.TimeLimitSeconds, &solution, &plan.ErrorMessage, &plan.CreatedAt,
		&plan.CompletedAt,
	)
	plan.Solution = solution
	return plan, err
}

func (r *PostgresRepository) Create(ctx context.Context, params CreateParams) (Plan, error) {
	plan, err := scanPlan(r.db.QueryRowContext(ctx, `INSERT INTO plans (
		source_plan_id, status, solver_name, seed, time_limit_seconds
	) VALUES ($1, 'running', $2, $3, $4) RETURNING `+planColumns,
		params.SourcePlanID, params.SolverName, params.Seed, params.TimeLimitSeconds,
	))
	if err != nil {
		return Plan{}, fmt.Errorf("create plan: %w", err)
	}
	return plan, nil
}

type solutionSnapshot struct {
	Status string `json:"status"`
	Routes []struct {
		EngineerID          string          `json:"engineer_id"`
		DepartureMinutes    int             `json:"departure_minutes"`
		FinishMinutes       int             `json:"finish_minutes"`
		TotalTravelMinutes  int             `json:"total_travel_minutes"`
		TotalWaitingMinutes int             `json:"total_waiting_minutes"`
		TotalServiceMinutes int             `json:"total_service_minutes"`
		TotalDistanceKM     float64         `json:"total_distance_km"`
		Geometry            json.RawMessage `json:"geometry"`
		Stops               []struct {
			Sequence            int     `json:"sequence"`
			JobID               string  `json:"job_id"`
			FromLocationID      string  `json:"from_location_id"`
			TravelMinutes       int     `json:"travel_minutes"`
			DistanceKM          float64 `json:"distance_km"`
			ArrivalMinutes      int     `json:"arrival_minutes"`
			ServiceStartMinutes int     `json:"service_start_minutes"`
			ServiceEndMinutes   int     `json:"service_end_minutes"`
			WaitingMinutes      int     `json:"waiting_minutes"`
		} `json:"stops"`
	} `json:"routes"`
	Unassigned []struct {
		JobID   string `json:"job_id"`
		Code    string `json:"code"`
		Message string `json:"message"`
	} `json:"unassigned"`
}

func (r *PostgresRepository) Complete(ctx context.Context, id uuid.UUID, solution json.RawMessage) (Plan, error) {
	var snapshot solutionSnapshot
	if err := json.Unmarshal(solution, &snapshot); err != nil {
		return Plan{}, fmt.Errorf("decode solution snapshot: %w", err)
	}
	if snapshot.Status == "" {
		return Plan{}, errors.New("solution status is empty")
	}
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return Plan{}, fmt.Errorf("begin complete plan: %w", err)
	}
	defer tx.Rollback()
	result, err := tx.ExecContext(ctx, `UPDATE plans
		SET status = $2, solution = $3::jsonb, completed_at = now(), error_message = NULL
		WHERE id = $1`, id, snapshot.Status, string(solution))
	if err != nil {
		return Plan{}, fmt.Errorf("complete plan: %w", err)
	}
	count, err := result.RowsAffected()
	if err != nil || count == 0 {
		return Plan{}, ErrNotFound
	}
	for _, route := range snapshot.Routes {
		brigadeID, err := uuid.Parse(route.EngineerID)
		if err != nil {
			return Plan{}, fmt.Errorf("invalid brigade id in solution: %w", err)
		}
		var routeID uuid.UUID
		err = tx.QueryRowContext(ctx, `INSERT INTO plan_routes (
			plan_id, brigade_id, departure_minutes, finish_minutes,
			total_travel_minutes, total_waiting_minutes, total_service_minutes,
			total_distance_km, geometry
		) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NULLIF($9::text, '')::jsonb) RETURNING id`,
			id, brigadeID, route.DepartureMinutes, route.FinishMinutes,
			route.TotalTravelMinutes, route.TotalWaitingMinutes, route.TotalServiceMinutes,
			route.TotalDistanceKM, string(route.Geometry),
		).Scan(&routeID)
		if err != nil {
			return Plan{}, fmt.Errorf("insert plan route: %w", err)
		}
		for _, stop := range route.Stops {
			requestID, err := uuid.Parse(stop.JobID)
			if err != nil {
				return Plan{}, fmt.Errorf("invalid request id in solution: %w", err)
			}
			_, err = tx.ExecContext(ctx, `INSERT INTO plan_stops (
				route_id, request_id, sequence, from_location_id, travel_minutes,
				distance_km, arrival_minutes, service_start_minutes,
				service_end_minutes, waiting_minutes
			) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
				routeID, requestID, stop.Sequence, stop.FromLocationID, stop.TravelMinutes,
				stop.DistanceKM, stop.ArrivalMinutes, stop.ServiceStartMinutes,
				stop.ServiceEndMinutes, stop.WaitingMinutes,
			)
			if err != nil {
				return Plan{}, fmt.Errorf("insert plan stop: %w", err)
			}
			if _, err = tx.ExecContext(ctx, `UPDATE requests SET status = 'planned'
				WHERE id = $1 AND status = 'pending'`, requestID); err != nil {
				return Plan{}, fmt.Errorf("mark request planned: %w", err)
			}
		}
	}
	for _, item := range snapshot.Unassigned {
		requestID, err := uuid.Parse(item.JobID)
		if err != nil {
			return Plan{}, fmt.Errorf("invalid unassigned request id: %w", err)
		}
		if _, err = tx.ExecContext(ctx, `INSERT INTO plan_unassigned
			(plan_id, request_id, code, message) VALUES ($1,$2,$3,$4)`,
			id, requestID, item.Code, item.Message,
		); err != nil {
			return Plan{}, fmt.Errorf("insert unassigned request: %w", err)
		}
	}
	if err = tx.Commit(); err != nil {
		return Plan{}, fmt.Errorf("commit completed plan: %w", err)
	}
	return r.Get(ctx, id)
}

func (r *PostgresRepository) Fail(ctx context.Context, id uuid.UUID, message string) (Plan, error) {
	plan, err := scanPlan(r.db.QueryRowContext(ctx, `UPDATE plans
		SET status = 'error', error_message = $2, completed_at = now()
		WHERE id = $1 RETURNING `+planColumns, id, message))
	if errors.Is(err, sql.ErrNoRows) {
		return Plan{}, ErrNotFound
	}
	if err != nil {
		return Plan{}, fmt.Errorf("fail plan: %w", err)
	}
	return plan, nil
}

func (r *PostgresRepository) Get(ctx context.Context, id uuid.UUID) (Plan, error) {
	plan, err := scanPlan(r.db.QueryRowContext(ctx,
		"SELECT "+planColumns+" FROM plans WHERE id = $1", id,
	))
	if errors.Is(err, sql.ErrNoRows) {
		return Plan{}, ErrNotFound
	}
	if err != nil {
		return Plan{}, fmt.Errorf("get plan: %w", err)
	}
	return plan, nil
}

func (r *PostgresRepository) List(ctx context.Context) ([]Plan, error) {
	rows, err := r.db.QueryContext(ctx, "SELECT "+planColumns+" FROM plans ORDER BY created_at DESC LIMIT 50")
	if err != nil {
		return nil, fmt.Errorf("list plans: %w", err)
	}
	defer rows.Close()
	items := make([]Plan, 0)
	for rows.Next() {
		item, err := scanPlan(rows)
		if err != nil {
			return nil, fmt.Errorf("scan plan: %w", err)
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (r *PostgresRepository) CreateEvent(ctx context.Context, planID uuid.UUID, eventType string, payload json.RawMessage) (ReplanEvent, error) {
	var event ReplanEvent
	err := r.db.QueryRowContext(ctx, `INSERT INTO replan_events (plan_id, event_type, payload)
		VALUES ($1,$2,$3::jsonb) RETURNING id, plan_id, resulting_plan_id, event_type, payload,
		status, error_message, created_at, processed_at`, planID, eventType, string(payload),
	).Scan(&event.ID, &event.PlanID, &event.ResultingPlanID, &event.Type, &event.Payload,
		&event.Status, &event.ErrorMessage, &event.CreatedAt, &event.ProcessedAt)
	if err != nil {
		return ReplanEvent{}, fmt.Errorf("create replan event: %w", err)
	}
	return event, nil
}

func (r *PostgresRepository) CompleteEvent(ctx context.Context, eventID, resultingPlanID uuid.UUID) error {
	_, err := r.db.ExecContext(ctx, `UPDATE replan_events SET status = 'applied',
		resulting_plan_id = $2, processed_at = now() WHERE id = $1`, eventID, resultingPlanID)
	return err
}

func (r *PostgresRepository) FailEvent(ctx context.Context, eventID uuid.UUID, message string) error {
	_, err := r.db.ExecContext(ctx, `UPDATE replan_events SET status = 'failed',
		error_message = $2, processed_at = now() WHERE id = $1`, eventID, message)
	return err
}
