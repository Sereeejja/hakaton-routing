CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id text UNIQUE,
    address text NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    service_minutes integer NOT NULL CHECK (service_minutes > 0),
    window_start time NOT NULL,
    window_end time NOT NULL,
    required_skill text NOT NULL CHECK (required_skill IN ('connection', 'local', 'emergency')),
    required_transport text CHECK (required_transport IS NULL OR required_transport IN ('car', 'walk', 'bicycle', 'public_transit')),
    priority text NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'urgent')),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'planned', 'completed', 'canceled')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (window_start <= window_end)
);

CREATE INDEX requests_status_idx ON requests(status);
CREATE INDEX requests_created_at_idx ON requests(created_at DESC);

CREATE TABLE brigades (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    start_address text NOT NULL,
    start_latitude double precision NOT NULL CHECK (start_latitude BETWEEN -90 AND 90),
    start_longitude double precision NOT NULL CHECK (start_longitude BETWEEN -180 AND 180),
    shift_start time NOT NULL,
    shift_end time NOT NULL,
    transport text NOT NULL CHECK (transport IN ('car', 'walk', 'bicycle', 'public_transit')),
    status text NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'unavailable')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (shift_start <= shift_end)
);

CREATE INDEX brigades_status_idx ON brigades(status);

CREATE TABLE brigade_skills (
    brigade_id uuid NOT NULL REFERENCES brigades(id) ON DELETE CASCADE,
    skill text NOT NULL CHECK (skill IN ('connection', 'local', 'emergency')),
    PRIMARY KEY (brigade_id, skill)
);

CREATE TABLE plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_plan_id uuid REFERENCES plans(id) ON DELETE SET NULL,
    status text NOT NULL CHECK (status IN ('running', 'feasible', 'partial', 'infeasible', 'error')),
    solver_name text NOT NULL,
    seed integer NOT NULL,
    time_limit_seconds double precision NOT NULL CHECK (time_limit_seconds > 0),
    solution jsonb,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX plans_created_at_idx ON plans(created_at DESC);
CREATE INDEX plans_status_idx ON plans(status);

CREATE TABLE plan_routes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    brigade_id uuid NOT NULL REFERENCES brigades(id),
    departure_minutes integer NOT NULL,
    finish_minutes integer NOT NULL,
    total_travel_minutes integer NOT NULL,
    total_waiting_minutes integer NOT NULL,
    total_service_minutes integer NOT NULL,
    total_distance_km double precision NOT NULL,
    geometry jsonb,
    UNIQUE (plan_id, brigade_id)
);

CREATE TABLE plan_stops (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id uuid NOT NULL REFERENCES plan_routes(id) ON DELETE CASCADE,
    request_id uuid NOT NULL REFERENCES requests(id),
    sequence integer NOT NULL CHECK (sequence > 0),
    from_location_id text NOT NULL,
    travel_minutes integer NOT NULL,
    distance_km double precision NOT NULL,
    arrival_minutes integer NOT NULL,
    service_start_minutes integer NOT NULL,
    service_end_minutes integer NOT NULL,
    waiting_minutes integer NOT NULL,
    UNIQUE (route_id, sequence),
    UNIQUE (route_id, request_id)
);

CREATE INDEX plan_stops_request_idx ON plan_stops(request_id);

CREATE TABLE plan_unassigned (
    plan_id uuid NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    request_id uuid NOT NULL REFERENCES requests(id),
    code text NOT NULL,
    message text NOT NULL,
    PRIMARY KEY (plan_id, request_id)
);

CREATE TABLE replan_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    resulting_plan_id uuid REFERENCES plans(id) ON DELETE SET NULL,
    event_type text NOT NULL CHECK (event_type IN ('cancel_request', 'brigade_unavailable', 'new_urgent_request')),
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'applied', 'failed')),
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz
);

CREATE INDEX replan_events_plan_idx ON replan_events(plan_id, created_at DESC);

CREATE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER requests_touch_updated_at
BEFORE UPDATE ON requests
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER brigades_touch_updated_at
BEFORE UPDATE ON brigades
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
