package requests

import "testing"

func TestValidateCreate(t *testing.T) {
	valid := CreateDTO{
		Address: "Москва", Latitude: 55.75, Longitude: 37.61,
		ServiceMinutes: 30, WindowStart: "10:00", WindowEnd: "12:00",
		RequiredSkill: "local", Priority: "normal",
	}
	if err := validateCreate(valid); err != nil {
		t.Fatalf("valid DTO rejected: %v", err)
	}
	invalid := valid
	invalid.WindowEnd = "09:00"
	if err := validateCreate(invalid); err == nil {
		t.Fatal("invalid time window accepted")
	}
}
