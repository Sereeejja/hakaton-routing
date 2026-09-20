package routing

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type OSRMClient struct {
	baseURL string
	http    *http.Client
}

func NewOSRMClient(baseURL string) *OSRMClient {
	return &OSRMClient{
		baseURL: strings.TrimRight(baseURL, "/"),
		http:    &http.Client{Timeout: 10 * time.Second},
	}
}

func (c *OSRMClient) Route(ctx context.Context, coordinates []Coordinate) (json.RawMessage, error) {
	if len(coordinates) < 2 {
		return StraightLineClient{}.Route(ctx, coordinates)
	}
	parts := make([]string, 0, len(coordinates))
	for _, coordinate := range coordinates {
		parts = append(parts, strconv.FormatFloat(coordinate.Longitude, 'f', 6, 64)+","+
			strconv.FormatFloat(coordinate.Latitude, 'f', 6, 64))
	}
	endpoint := c.baseURL + "/route/v1/driving/" + strings.Join(parts, ";")
	query := url.Values{"overview": {"full"}, "geometries": {"geojson"}, "steps": {"false"}}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint+"?"+query.Encode(), nil)
	if err != nil {
		return nil, fmt.Errorf("create OSRM request: %w", err)
	}
	req.Header.Set("User-Agent", "hakaton-routing/0.1")
	response, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("call OSRM: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("OSRM status %d", response.StatusCode)
	}
	var payload struct {
		Code   string `json:"code"`
		Routes []struct {
			Geometry json.RawMessage `json:"geometry"`
		} `json:"routes"`
	}
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return nil, fmt.Errorf("decode OSRM response: %w", err)
	}
	if payload.Code != "Ok" || len(payload.Routes) == 0 {
		return nil, fmt.Errorf("OSRM route unavailable: %s", payload.Code)
	}
	return payload.Routes[0].Geometry, nil
}
