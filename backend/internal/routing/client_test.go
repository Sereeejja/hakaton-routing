package routing

import (
	"context"
	"encoding/json"
	"testing"
)

func TestStraightLineClientReturnsGeoJSONLongitudeFirst(t *testing.T) {
	geometry, err := (StraightLineClient{}).Route(context.Background(), []Coordinate{
		{Latitude: 55.75, Longitude: 37.61},
		{Latitude: 55.76, Longitude: 37.62},
	})
	if err != nil {
		t.Fatalf("Route() error = %v", err)
	}
	var result struct {
		Type        string       `json:"type"`
		Coordinates [][2]float64 `json:"coordinates"`
	}
	if err := json.Unmarshal(geometry, &result); err != nil {
		t.Fatal(err)
	}
	if result.Type != "LineString" || result.Coordinates[0] != [2]float64{37.61, 55.75} {
		t.Fatalf("unexpected geometry: %s", geometry)
	}
}
