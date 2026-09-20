package brigades

import "testing"

func TestValidateCreate(t *testing.T) {
	valid := CreateDTO{
		Name: "Бригада 1", StartAddress: "Москва", StartLatitude: 55.75,
		StartLongitude: 37.61, ShiftStart: "09:00", ShiftEnd: "18:00",
		Skills: []string{"local"}, Transport: "car",
	}
	if err := validateCreate(valid); err != nil {
		t.Fatalf("valid DTO rejected: %v", err)
	}
	invalid := valid
	invalid.Skills = nil
	if err := validateCreate(invalid); err == nil {
		t.Fatal("brigade without skills accepted")
	}
}
