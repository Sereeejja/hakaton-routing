package planning

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/Sereeejja/hakaton-routing/backend/internal/brigades"
	"github.com/Sereeejja/hakaton-routing/backend/internal/plans"
	"github.com/Sereeejja/hakaton-routing/backend/internal/requests"
	"github.com/Sereeejja/hakaton-routing/backend/internal/routing"
	"github.com/google/uuid"
)

var ErrValidation = errors.New("planning validation failed")

type Service struct {
	requests       *requests.Service
	brigades       *brigades.Service
	plans          plans.Repository
	planner        Planner
	routing        routing.Client
	routingBaseURL string
}

func NewService(
	requestService *requests.Service,
	brigadeService *brigades.Service,
	planRepository plans.Repository,
	planner Planner,
	routingClient routing.Client,
	routingBaseURL string,
) *Service {
	return &Service{
		requests:       requestService,
		brigades:       brigadeService,
		plans:          planRepository,
		planner:        planner,
		routing:        routingClient,
		routingBaseURL: routingBaseURL,
	}
}

func (s *Service) Run(ctx context.Context, dto RunDTO) (plans.Plan, error) {
	if dto.SolverName == "" {
		dto.SolverName = "ortools"
	}
	if dto.TimeLimitSeconds == 0 {
		dto.TimeLimitSeconds = 10
	}
	if dto.Seed == 0 {
		dto.Seed = 42
	}
	if !oneOf(dto.SolverName, "greedy", "improved_greedy", "ortools", "hgs") {
		return plans.Plan{}, fmt.Errorf("%w: unknown solver_name", ErrValidation)
	}
	if dto.TimeLimitSeconds <= 0 || dto.TimeLimitSeconds > 120 {
		return plans.Plan{}, fmt.Errorf("%w: time_limit_seconds must be between 0 and 120", ErrValidation)
	}
	allRequests, err := s.requests.List(ctx)
	if err != nil {
		return plans.Plan{}, err
	}
	allBrigades, err := s.brigades.List(ctx)
	if err != nil {
		return plans.Plan{}, err
	}
	selectedRequests := selectRequests(allRequests, dto.RequestIDs)
	selectedBrigades := selectBrigades(allBrigades, dto.BrigadeIDs)
	if len(selectedRequests) == 0 {
		return plans.Plan{}, fmt.Errorf("%w: no active requests selected", ErrValidation)
	}
	if len(selectedBrigades) == 0 {
		return plans.Plan{}, fmt.Errorf("%w: no available brigades selected", ErrValidation)
	}
	plan, err := s.plans.Create(ctx, plans.CreateParams{
		SourcePlanID: dto.SourcePlanID, SolverName: dto.SolverName,
		Seed: dto.Seed, TimeLimitSeconds: dto.TimeLimitSeconds,
	})
	if err != nil {
		return plans.Plan{}, err
	}
	input := buildSolverInput(plan.ID, selectedRequests, selectedBrigades, dto, s.routingBaseURL)
	if dto.SourcePlanID != nil {
		input.PreviousAssignments = s.previousAssignments(ctx, *dto.SourcePlanID)
	}
	result, err := s.planner.Solve(ctx, input)
	if err != nil {
		failed, failErr := s.plans.Fail(ctx, plan.ID, err.Error())
		if failErr != nil {
			return plans.Plan{}, fmt.Errorf("%v; record failure: %w", err, failErr)
		}
		return failed, err
	}
	s.enrichGeometry(ctx, &result, selectedRequests, selectedBrigades)
	snapshot, err := json.Marshal(result)
	if err != nil {
		return plans.Plan{}, fmt.Errorf("encode solution: %w", err)
	}
	completed, err := s.plans.Complete(ctx, plan.ID, snapshot)
	if err != nil {
		_, _ = s.plans.Fail(ctx, plan.ID, err.Error())
		return plans.Plan{}, err
	}
	return completed, nil
}

func buildSolverInput(
	id uuid.UUID,
	requestItems []requests.Request,
	brigadeItems []brigades.Brigade,
	dto RunDTO,
	routingBaseURL string,
) SolverInput {
	input := SolverInput{
		ProblemID: id.String(),
		Locations: make([]Location, 0, len(requestItems)+len(brigadeItems)),
		Jobs:      make([]Job, 0, len(requestItems)),
		Engineers: make([]Engineer, 0, len(brigadeItems)),
		Options: SolverOptions{
			SolverName: dto.SolverName, TimeLimitSeconds: dto.TimeLimitSeconds,
			Seed: dto.Seed, TravelSpeedKMH: 30, RoutingBaseURL: routingBaseURL,
		},
	}
	for _, item := range requestItems {
		locationID := "request:" + item.ID.String()
		input.Locations = append(input.Locations, Location{
			ID: locationID, Address: item.Address, Latitude: item.Latitude, Longitude: item.Longitude,
		})
		input.Jobs = append(input.Jobs, Job{
			ID: item.ID.String(), LocationID: locationID, ServiceMinutes: item.ServiceMinutes,
			WindowStart: item.WindowStart, WindowEnd: item.WindowEnd,
			RequiredSkill: item.RequiredSkill, RequiredTransport: item.RequiredTransport,
			Priority: item.Priority, Metadata: item.Metadata,
		})
	}
	for _, item := range brigadeItems {
		locationID := "brigade:" + item.ID.String() + ":start"
		input.Locations = append(input.Locations, Location{
			ID: locationID, Address: item.StartAddress,
			Latitude: item.StartLatitude, Longitude: item.StartLongitude,
		})
		input.Engineers = append(input.Engineers, Engineer{
			ID: item.ID.String(), StartLocationID: locationID,
			ShiftStart: item.ShiftStart, ShiftEnd: item.ShiftEnd,
			Skills: item.Skills, Transport: item.Transport, WorkSchedule: item.WorkSchedule,
		})
	}
	return input
}

func (s *Service) previousAssignments(ctx context.Context, planID uuid.UUID) map[string]string {
	plan, err := s.plans.Get(ctx, planID)
	if err != nil || len(plan.Solution) == 0 {
		return nil
	}
	var result Result
	if json.Unmarshal(plan.Solution, &result) != nil {
		return nil
	}
	assignments := make(map[string]string)
	for _, route := range result.Routes {
		for _, stop := range route.Stops {
			assignments[stop.JobID] = route.EngineerID
		}
	}
	return assignments
}

func (s *Service) enrichGeometry(ctx context.Context, result *Result, requestItems []requests.Request, brigadeItems []brigades.Brigade) {
	requestCoordinates := make(map[string]routing.Coordinate, len(requestItems))
	for _, item := range requestItems {
		requestCoordinates[item.ID.String()] = routing.Coordinate{Latitude: item.Latitude, Longitude: item.Longitude}
	}
	brigadeCoordinates := make(map[string]routing.Coordinate, len(brigadeItems))
	for _, item := range brigadeItems {
		brigadeCoordinates[item.ID.String()] = routing.Coordinate{Latitude: item.StartLatitude, Longitude: item.StartLongitude}
	}
	for index := range result.Routes {
		route := &result.Routes[index]
		if len(route.Stops) == 0 {
			continue
		}
		coordinates := []routing.Coordinate{brigadeCoordinates[route.EngineerID]}
		for _, stop := range route.Stops {
			coordinates = append(coordinates, requestCoordinates[stop.JobID])
		}
		geometry, err := s.routing.Route(ctx, coordinates)
		if err != nil {
			result.Warnings = append(result.Warnings, "route geometry: "+err.Error())
			continue
		}
		route.Geometry = geometry
	}
}

func selectRequests(items []requests.Request, ids []uuid.UUID) []requests.Request {
	selected := make(map[uuid.UUID]struct{}, len(ids))
	for _, id := range ids {
		selected[id] = struct{}{}
	}
	result := make([]requests.Request, 0, len(items))
	for _, item := range items {
		_, explicitlySelected := selected[item.ID]
		active := item.Status == "pending" || item.Status == "planned"
		if active && (len(selected) == 0 || explicitlySelected) {
			result = append(result, item)
		}
	}
	return result
}

func selectBrigades(items []brigades.Brigade, ids []uuid.UUID) []brigades.Brigade {
	selected := make(map[uuid.UUID]struct{}, len(ids))
	for _, id := range ids {
		selected[id] = struct{}{}
	}
	result := make([]brigades.Brigade, 0, len(items))
	for _, item := range items {
		_, explicitlySelected := selected[item.ID]
		if item.Status == "available" && (len(selected) == 0 || explicitlySelected) {
			result = append(result, item)
		}
	}
	return result
}

func oneOf(value string, candidates ...string) bool {
	for _, candidate := range candidates {
		if value == candidate {
			return true
		}
	}
	return false
}
