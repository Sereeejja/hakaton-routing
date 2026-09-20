package brigades

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/google/uuid"
)

var ErrNotFound = errors.New("brigade not found")

type Repository interface {
	Create(context.Context, CreateDTO) (Brigade, error)
	List(context.Context) ([]Brigade, error)
	Get(context.Context, uuid.UUID) (Brigade, error)
	UpdateStatus(context.Context, uuid.UUID, string) (Brigade, error)
}

type PostgresRepository struct {
	db *sql.DB
}

func NewPostgresRepository(db *sql.DB) *PostgresRepository {
	return &PostgresRepository{db: db}
}

const brigadeColumns = `
	b.id, b.name, b.start_address, b.start_latitude, b.start_longitude,
	to_char(b.shift_start, 'HH24:MI'), to_char(b.shift_end, 'HH24:MI'),
	COALESCE((SELECT jsonb_agg(bs.skill ORDER BY bs.skill) FROM brigade_skills bs WHERE bs.brigade_id = b.id), '[]'::jsonb),
	b.transport, b.status, b.metadata, b.created_at, b.updated_at`

func scanBrigade(scanner interface{ Scan(...any) error }) (Brigade, error) {
	var item Brigade
	var skillsJSON []byte
	err := scanner.Scan(
		&item.ID, &item.Name, &item.StartAddress, &item.StartLatitude,
		&item.StartLongitude, &item.ShiftStart, &item.ShiftEnd, &skillsJSON,
		&item.Transport, &item.Status, &item.Metadata, &item.CreatedAt, &item.UpdatedAt,
	)
	if err == nil {
		err = json.Unmarshal(skillsJSON, &item.Skills)
	}
	return item, err
}

func (r *PostgresRepository) Create(ctx context.Context, dto CreateDTO) (Brigade, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return Brigade{}, fmt.Errorf("begin create brigade: %w", err)
	}
	defer tx.Rollback()
	metadata := dto.Metadata
	if len(metadata) == 0 {
		metadata = []byte(`{}`)
	}
	var id uuid.UUID
	err = tx.QueryRowContext(ctx, `INSERT INTO brigades (
		name, start_address, start_latitude, start_longitude, shift_start,
		shift_end, transport, metadata
	) VALUES ($1, $2, $3, $4, $5::time, $6::time, $7, $8::jsonb) RETURNING id`,
		dto.Name, dto.StartAddress, dto.StartLatitude, dto.StartLongitude,
		dto.ShiftStart, dto.ShiftEnd, dto.Transport, string(metadata),
	).Scan(&id)
	if err != nil {
		return Brigade{}, fmt.Errorf("insert brigade: %w", err)
	}
	for _, skill := range dto.Skills {
		if _, err = tx.ExecContext(ctx,
			"INSERT INTO brigade_skills(brigade_id, skill) VALUES ($1, $2)", id, skill,
		); err != nil {
			return Brigade{}, fmt.Errorf("insert brigade skill: %w", err)
		}
	}
	if err = tx.Commit(); err != nil {
		return Brigade{}, fmt.Errorf("commit brigade: %w", err)
	}
	return r.Get(ctx, id)
}

func (r *PostgresRepository) List(ctx context.Context) ([]Brigade, error) {
	rows, err := r.db.QueryContext(ctx, "SELECT "+brigadeColumns+" FROM brigades b ORDER BY b.created_at DESC")
	if err != nil {
		return nil, fmt.Errorf("list brigades: %w", err)
	}
	defer rows.Close()
	items := make([]Brigade, 0)
	for rows.Next() {
		item, err := scanBrigade(rows)
		if err != nil {
			return nil, fmt.Errorf("scan brigade: %w", err)
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (r *PostgresRepository) Get(ctx context.Context, id uuid.UUID) (Brigade, error) {
	item, err := scanBrigade(r.db.QueryRowContext(ctx,
		"SELECT "+brigadeColumns+" FROM brigades b WHERE b.id = $1", id,
	))
	if errors.Is(err, sql.ErrNoRows) {
		return Brigade{}, ErrNotFound
	}
	if err != nil {
		return Brigade{}, fmt.Errorf("get brigade: %w", err)
	}
	return item, nil
}

func (r *PostgresRepository) UpdateStatus(ctx context.Context, id uuid.UUID, status string) (Brigade, error) {
	result, err := r.db.ExecContext(ctx, "UPDATE brigades SET status = $2 WHERE id = $1", id, status)
	if err != nil {
		return Brigade{}, fmt.Errorf("update brigade status: %w", err)
	}
	count, err := result.RowsAffected()
	if err != nil {
		return Brigade{}, fmt.Errorf("read updated brigade count: %w", err)
	}
	if count == 0 {
		return Brigade{}, ErrNotFound
	}
	return r.Get(ctx, id)
}
