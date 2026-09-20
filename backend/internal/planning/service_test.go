package planning

import (
	"testing"

	"github.com/Sereeejja/hakaton-routing/backend/internal/requests"
	"github.com/google/uuid"
)

func TestSelectRequestsExcludesTerminalStatuses(t *testing.T) {
	pendingID := uuid.New()
	items := []requests.Request{
		{ID: pendingID, Status: "pending"},
		{ID: uuid.New(), Status: "planned"},
		{ID: uuid.New(), Status: "completed"},
		{ID: uuid.New(), Status: "canceled"},
	}
	selected := selectRequests(items, nil)
	if len(selected) != 2 || selected[0].ID != pendingID {
		t.Fatalf("unexpected active requests: %#v", selected)
	}
}
