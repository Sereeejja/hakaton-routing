package replanning

import (
	"encoding/json"
	"testing"

	"github.com/Sereeejja/hakaton-routing/backend/internal/requests"
)

func TestPrepareUrgentRequestBuildsReactionWindow(t *testing.T) {
	dto, err := prepareUrgentRequest(requests.CreateDTO{
		Address: "Москва", Latitude: 55.75, Longitude: 37.61, ServiceMinutes: 80,
	}, "14:25", 0)
	if err != nil {
		t.Fatalf("prepare urgent request: %v", err)
	}
	if dto.Priority != "urgent" || dto.RequiredSkill != "emergency" {
		t.Fatalf("unexpected urgent defaults: %#v", dto)
	}
	if dto.WindowStart != "14:25" || dto.WindowEnd != "16:25" {
		t.Fatalf("unexpected reaction window: %s-%s", dto.WindowStart, dto.WindowEnd)
	}
	var metadata map[string]any
	if err := json.Unmarshal(dto.Metadata, &metadata); err != nil {
		t.Fatalf("decode metadata: %v", err)
	}
	if metadata["reaction_sla_minutes"] != float64(120) {
		t.Fatalf("unexpected SLA metadata: %#v", metadata)
	}
}

func TestPrepareUrgentRequestRejectsSLAOutsideOneToTwoHours(t *testing.T) {
	_, err := prepareUrgentRequest(requests.CreateDTO{}, "10:00", 30)
	if err == nil {
		t.Fatal("reaction SLA below one hour was accepted")
	}
}
