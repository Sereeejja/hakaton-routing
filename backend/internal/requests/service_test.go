package requests

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/google/uuid"
)

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

type deleteRepositoryStub struct {
	deletedID uuid.UUID
	count     int64
	err       error
}

func (r *deleteRepositoryStub) Create(context.Context, CreateDTO) (Request, error) {
	return Request{}, errors.New("not implemented")
}
func (r *deleteRepositoryStub) List(context.Context) ([]Request, error) {
	return []Request{}, nil
}
func (r *deleteRepositoryStub) Get(context.Context, uuid.UUID) (Request, error) {
	return Request{}, ErrNotFound
}
func (r *deleteRepositoryStub) UpdateStatus(context.Context, uuid.UUID, string) (Request, error) {
	return Request{}, errors.New("not implemented")
}
func (r *deleteRepositoryStub) Delete(_ context.Context, id uuid.UUID) error {
	r.deletedID = id
	return r.err
}
func (r *deleteRepositoryStub) DeleteAll(context.Context) (int64, error) {
	return r.count, r.err
}

func TestDeleteRequestEndpoint(t *testing.T) {
	id := uuid.New()
	repository := &deleteRepositoryStub{}
	handler := NewHandler(NewService(repository))
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodDelete, "/"+id.String(), nil)

	handler.Routes().ServeHTTP(recorder, req)

	if recorder.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want %d; body=%s", recorder.Code, http.StatusNoContent, recorder.Body.String())
	}
	if repository.deletedID != id {
		t.Fatalf("deleted id = %s, want %s", repository.deletedID, id)
	}
}

func TestDeleteRequestEndpointReturnsNotFound(t *testing.T) {
	repository := &deleteRepositoryStub{err: ErrNotFound}
	handler := NewHandler(NewService(repository))
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodDelete, "/"+uuid.NewString(), nil)

	handler.Routes().ServeHTTP(recorder, req)

	if recorder.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want %d; body=%s", recorder.Code, http.StatusNotFound, recorder.Body.String())
	}
}

func TestDeleteAllRequestsEndpoint(t *testing.T) {
	repository := &deleteRepositoryStub{count: 7}
	handler := NewHandler(NewService(repository))
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodDelete, "/", nil)

	handler.Routes().ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d; body=%s", recorder.Code, http.StatusOK, recorder.Body.String())
	}
	if body := recorder.Body.String(); body != "{\"deleted_count\":7}\n" {
		t.Fatalf("body = %q", body)
	}
}
