import type {
  Brigade,
  CreateBrigadeInput,
  CreateRequestInput,
  Plan,
  RunPlanInput,
  ServiceRequest,
} from "../types/domain";

const API_ROOT = "/api/v1";

export class APIError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  const text = await response.text();
  let payload: unknown = null;

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      throw new APIError("Сервер вернул некорректный ответ", response.status);
    }
  }

  if (!response.ok) {
    const errorPayload = payload as { message?: string } | null;
    throw new APIError(errorPayload?.message ?? `HTTP ${response.status}`, response.status);
  }
  return payload as T;
}

export const api = {
  requests: {
    list: () => request<ServiceRequest[]>("/requests/"),
    create: (input: CreateRequestInput) =>
      request<ServiceRequest>("/requests/", { method: "POST", body: JSON.stringify(input) }),
    delete: (id: string) => request<void>(`/requests/${id}`, { method: "DELETE" }),
    clear: () => request<{ deleted_count: number }>("/requests/", { method: "DELETE" }),
  },
  brigades: {
    list: () => request<Brigade[]>("/brigades/"),
    create: (input: CreateBrigadeInput) =>
      request<Brigade>("/brigades/", { method: "POST", body: JSON.stringify(input) }),
  },
  plans: {
    list: () => request<Plan[]>("/plans/"),
    create: (input: RunPlanInput) =>
      request<Plan>("/plans/", { method: "POST", body: JSON.stringify(input) }),
    applyEvent: (planId: string, type: string, payload: Record<string, string>) =>
      request<{ event: unknown; plan: Plan }>(`/plans/${planId}/events`, {
        method: "POST",
        body: JSON.stringify({ type, payload }),
      }),
  },
};
