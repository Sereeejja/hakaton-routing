package requests

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	"github.com/google/uuid"
)

var ErrNotFound = errors.New("request not found")

type Repository interface {
	Create(context.Context, CreateDTO) (Request, error)
	List(context.Context) ([]Request, error)
	Get(context.Context, uuid.UUID) (Request, error)
	UpdateStatus(context.Context, uuid.UUID, string) (Request, error)
	Delete(context.Context, uuid.UUID) error
	DeleteAll(context.Context) (int64, error)
}

type PostgresRepository struct {
	db *sql.DB
}

func NewPostgresRepository(db *sql.DB) *PostgresRepository {
	return &PostgresRepository{db: db}
}

const requestColumns = `
	id, external_id, address, latitude, longitude, service_minutes,
	to_char(window_start, 'HH24:MI'), to_char(window_end, 'HH24:MI'),
	required_skill, required_transport, priority, status, metadata, created_at, updated_at`

func scanRequest(scanner interface{ Scan(...any) error }) (Request, error) {
	var item Request
	err := scanner.Scan(
		&item.ID, &item.ExternalID, &item.Address, &item.Latitude, &item.Longitude,
		&item.ServiceMinutes, &item.WindowStart, &item.WindowEnd, &item.RequiredSkill,
		&item.RequiredTransport, &item.Priority, &item.Status, &item.Metadata,
		&item.CreatedAt, &item.UpdatedAt,
	)
	return item, err
}

func (r *PostgresRepository) Create(ctx context.Context, dto CreateDTO) (Request, error) {
	metadata := dto.Metadata
	if len(metadata) == 0 {
		metadata = []byte(`{}`)
	}
	query := `INSERT INTO requests (
		external_id, address, latitude, longitude, service_minutes,
		window_start, window_end, required_skill, required_transport, priority, metadata
	) VALUES (NULLIF($1, ''), $2, $3, $4, $5, $6::time, $7::time, $8, $9, $10, $11::jsonb)
	RETURNING ` + requestColumns
	item, err := scanRequest(r.db.QueryRowContext(ctx, query,
		dto.ExternalID, dto.Address, dto.Latitude, dto.Longitude, dto.ServiceMinutes,
		dto.WindowStart, dto.WindowEnd, dto.RequiredSkill, dto.RequiredTransport,
		dto.Priority, string(metadata),
	))
	if err != nil {
		return Request{}, fmt.Errorf("create request: %w", err)
	}
	return item, nil
}

func (r *PostgresRepository) List(ctx context.Context) ([]Request, error) {
	rows, err := r.db.QueryContext(ctx, "SELECT "+requestColumns+" FROM requests ORDER BY created_at DESC")
	if err != nil {
		return nil, fmt.Errorf("list requests: %w", err)
	}
	defer rows.Close()
	items := make([]Request, 0)
	for rows.Next() {
		item, err := scanRequest(rows)
		if err != nil {
			return nil, fmt.Errorf("scan request: %w", err)
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (r *PostgresRepository) Get(ctx context.Context, id uuid.UUID) (Request, error) {
	item, err := scanRequest(r.db.QueryRowContext(ctx,
		"SELECT "+requestColumns+" FROM requests WHERE id = $1", id,
	))
	if errors.Is(err, sql.ErrNoRows) {
		return Request{}, ErrNotFound
	}
	if err != nil {
		return Request{}, fmt.Errorf("get request: %w", err)
	}
	return item, nil
}

func (r *PostgresRepository) UpdateStatus(ctx context.Context, id uuid.UUID, status string) (Request, error) {
	item, err := scanRequest(r.db.QueryRowContext(ctx,
		"UPDATE requests SET status = $2 WHERE id = $1 RETURNING "+requestColumns, id, status,
	))
	if errors.Is(err, sql.ErrNoRows) {
		return Request{}, ErrNotFound
	}
	if err != nil {
		return Request{}, fmt.Errorf("update request status: %w", err)
	}
	return item, nil
}

func (r *PostgresRepository) Delete(ctx context.Context, id uuid.UUID) error {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin delete request: %w", err)
	}
	defer tx.Rollback()

	// A saved plan is an immutable snapshot of its input. Once one of its
	// requests is removed, the snapshot is no longer valid, so remove the whole
	// affected plan and let its routes/stops/events cascade.
	if _, err = tx.ExecContext(ctx, `DELETE FROM plans WHERE id IN (
		SELECT pr.plan_id
		FROM plan_routes pr
		JOIN plan_stops ps ON ps.route_id = pr.id
		WHERE ps.request_id = $1
		UNION
		SELECT plan_id FROM plan_unassigned WHERE request_id = $1
	)`, id); err != nil {
		return fmt.Errorf("delete request plans: %w", err)
	}
	result, err := tx.ExecContext(ctx, "DELETE FROM requests WHERE id = $1", id)
	if err != nil {
		return fmt.Errorf("delete request: %w", err)
	}
	count, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("delete request rows: %w", err)
	}
	if count == 0 {
		return ErrNotFound
	}
	if err = tx.Commit(); err != nil {
		return fmt.Errorf("commit delete request: %w", err)
	}
	return nil
}

func (r *PostgresRepository) DeleteAll(ctx context.Context) (int64, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return 0, fmt.Errorf("begin clear requests: %w", err)
	}
	defer tx.Rollback()

	// Plans refer to requests both relationally and inside their JSON snapshot.
	// Clearing requests therefore also clears plans, while brigades stay intact.
	if _, err = tx.ExecContext(ctx, "DELETE FROM plans"); err != nil {
		return 0, fmt.Errorf("clear request plans: %w", err)
	}
	result, err := tx.ExecContext(ctx, "DELETE FROM requests")
	if err != nil {
		return 0, fmt.Errorf("clear requests: %w", err)
	}
	count, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("clear request rows: %w", err)
	}
	if err = tx.Commit(); err != nil {
		return 0, fmt.Errorf("commit clear requests: %w", err)
	}
	return count, nil
}
