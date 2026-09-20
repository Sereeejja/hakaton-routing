package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/Sereeejja/hakaton-routing/backend/config"
	_ "github.com/Sereeejja/hakaton-routing/backend/docs"
	"github.com/Sereeejja/hakaton-routing/backend/internal/brigades"
	"github.com/Sereeejja/hakaton-routing/backend/internal/database"
	"github.com/Sereeejja/hakaton-routing/backend/internal/planning"
	"github.com/Sereeejja/hakaton-routing/backend/internal/plans"
	"github.com/Sereeejja/hakaton-routing/backend/internal/replanning"
	"github.com/Sereeejja/hakaton-routing/backend/internal/requests"
	"github.com/Sereeejja/hakaton-routing/backend/internal/routing"
	"github.com/Sereeejja/hakaton-routing/backend/internal/web"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	httpSwagger "github.com/swaggo/http-swagger/v2"
)

// @title Routing Planner API
// @version 0.1.0
// @description API заявок, бригад, планирования и оперативного перепланирования.
// @BasePath /api/v1
// @schemes http https
func main() {
	if err := run(); err != nil {
		slog.Error("server stopped", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	ctx := context.Background()
	db, err := database.Open(ctx, cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer db.Close()
	if cfg.AutoMigrate {
		if err := database.Migrate(ctx, db, cfg.MigrationsDir); err != nil {
			return err
		}
	}

	requestRepository := requests.NewPostgresRepository(db)
	requestService := requests.NewService(requestRepository)
	requestHandler := requests.NewHandler(requestService)

	brigadeRepository := brigades.NewPostgresRepository(db)
	brigadeService := brigades.NewService(brigadeRepository)
	brigadeHandler := brigades.NewHandler(brigadeService)

	planRepository := plans.NewPostgresRepository(db)
	planService := plans.NewService(planRepository)
	planHandler := plans.NewHandler(planService)

	var routeClient routing.Client = routing.StraightLineClient{}
	if cfg.OSRMBaseURL != "" {
		routeClient = routing.FallbackClient{
			Primary: routing.NewOSRMClient(cfg.OSRMBaseURL), Fallback: routing.StraightLineClient{},
		}
	}
	pythonPlanner := planning.NewPythonPlanner(cfg.SolverPython, cfg.SolverPythonPath, cfg.SolverTimeout)
	planningService := planning.NewService(
		requestService, brigadeService, planRepository, pythonPlanner, routeClient, cfg.OSRMBaseURL,
	)
	planningHandler := planning.NewHandler(planningService)
	replanningService := replanning.NewService(
		planRepository, requestService, brigadeService, planningService,
	)
	replanningHandler := replanning.NewHandler(replanningService)

	router := chi.NewRouter()
	router.Use(middleware.RequestID)
	router.Use(middleware.RealIP)
	router.Use(middleware.Logger)
	router.Use(middleware.Recoverer)
	router.Use(web.CORS)
	router.Get("/healthz", func(w http.ResponseWriter, r *http.Request) {
		if err := db.PingContext(r.Context()); err != nil {
			web.Error(w, http.StatusServiceUnavailable, "database_unavailable", err.Error())
			return
		}
		web.JSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	router.Get("/swagger/*", httpSwagger.Handler(httpSwagger.URL("/swagger/doc.json")).ServeHTTP)
	router.Route("/api/v1", func(api chi.Router) {
		api.Mount("/requests", requestHandler.Routes())
		api.Mount("/brigades", brigadeHandler.Routes())
		api.Route("/plans", func(route chi.Router) {
			route.Get("/", planHandler.List)
			route.Post("/", planningHandler.CreatePlan)
			route.Get("/{id}", planHandler.Get)
			route.Post("/{id}/events", replanningHandler.Apply)
		})
	})
	router.Handle("/*", web.SPA(cfg.FrontendDir))

	server := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      cfg.SolverTimeout + 15*time.Second,
		IdleTimeout:       60 * time.Second,
	}
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-stop
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()

	slog.Info("routing backend started", "address", cfg.HTTPAddr)
	err = server.ListenAndServe()
	if errors.Is(err, http.ErrServerClosed) {
		return nil
	}
	return err
}
