package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	HTTPAddr         string
	DatabaseURL      string
	MigrationsDir    string
	FrontendDir      string
	SolverPython     string
	SolverPythonPath string
	SolverTimeout    time.Duration
	OSRMBaseURL      string
	AutoMigrate      bool
}

func Load() (Config, error) {
	timeout, err := time.ParseDuration(env("SOLVER_TIMEOUT", "30s"))
	if err != nil {
		return Config{}, fmt.Errorf("parse SOLVER_TIMEOUT: %w", err)
	}
	autoMigrate, err := strconv.ParseBool(env("AUTO_MIGRATE", "true"))
	if err != nil {
		return Config{}, fmt.Errorf("parse AUTO_MIGRATE: %w", err)
	}
	return Config{
		HTTPAddr:         env("HTTP_ADDR", ":8080"),
		DatabaseURL:      env("DATABASE_URL", "postgres://routing:routing@localhost:5432/routing?sslmode=disable"),
		MigrationsDir:    env("MIGRATIONS_DIR", "migrations"),
		FrontendDir:      env("FRONTEND_DIR", "../frontend"),
		SolverPython:     env("SOLVER_PYTHON", "python3"),
		SolverPythonPath: env("SOLVER_PYTHONPATH", "../solver/src"),
		SolverTimeout:    timeout,
		OSRMBaseURL:      env("OSRM_BASE_URL", ""),
		AutoMigrate:      autoMigrate,
	}, nil
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
