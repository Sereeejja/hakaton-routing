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
