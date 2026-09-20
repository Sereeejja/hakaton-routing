package planning

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

type Planner interface {
	Solve(context.Context, SolverInput) (Result, error)
}

type PythonPlanner struct {
	python     string
	pythonPath string
	timeout    time.Duration
}

func NewPythonPlanner(python, pythonPath string, timeout time.Duration) *PythonPlanner {
	return &PythonPlanner{python: python, pythonPath: pythonPath, timeout: timeout}
}

func (p *PythonPlanner) Solve(ctx context.Context, input SolverInput) (Result, error) {
	payload, err := json.Marshal(input)
	if err != nil {
		return Result{}, fmt.Errorf("encode solver input: %w", err)
	}
	solverCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()
	command := exec.CommandContext(solverCtx, p.python, "-m", "routing_opt.backend_bridge")
	command.Stdin = bytes.NewReader(payload)
	command.Env = os.Environ()
	if p.pythonPath != "" {
		current := os.Getenv("PYTHONPATH")
		if current != "" {
			current = p.pythonPath + string(os.PathListSeparator) + current
		} else {
			current = p.pythonPath
		}
		command.Env = append(command.Env, "PYTHONPATH="+current)
	}
	var stdout, stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr
	if err := command.Run(); err != nil {
		if solverCtx.Err() != nil {
			return Result{}, fmt.Errorf("solver timeout: %w", solverCtx.Err())
		}
		message := strings.TrimSpace(stderr.String())
		if message == "" {
			message = err.Error()
		}
		return Result{}, fmt.Errorf("solver failed: %s", message)
	}
	var result Result
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		return Result{}, fmt.Errorf("decode solver output: %w", err)
	}
	return result, nil
}
