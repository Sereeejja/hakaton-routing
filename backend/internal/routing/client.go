package routing

import (
	"context"
	"encoding/json"
)

type Coordinate struct {
	Latitude  float64
	Longitude float64
}

type Client interface {
	Route(context.Context, []Coordinate) (json.RawMessage, error)
}

type StraightLineClient struct{}

func (StraightLineClient) Route(_ context.Context, coordinates []Coordinate) (json.RawMessage, error) {
	line := make([][2]float64, 0, len(coordinates))
	for _, coordinate := range coordinates {
		line = append(line, [2]float64{coordinate.Longitude, coordinate.Latitude})
	}
	return json.Marshal(map[string]any{
		"type":        "LineString",
		"coordinates": line,
	})
}

type FallbackClient struct {
	Primary  Client
	Fallback Client
}

func (c FallbackClient) Route(ctx context.Context, coordinates []Coordinate) (json.RawMessage, error) {
	geometry, err := c.Primary.Route(ctx, coordinates)
	if err == nil {
		return geometry, nil
	}
	return c.Fallback.Route(ctx, coordinates)
}
