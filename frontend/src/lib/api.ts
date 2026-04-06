const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("bridge_token")
      : null;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail ?? "Request failed");
  }

  return res.json() as Promise<T>;
}

export function login(email: string, password: string) {
  return apiFetch<{ access_token: string; token_type: string }>("/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe() {
  return apiFetch<{ email: string; role: string }>("/me");
}

// ---------------------------------------------------------------------------
// Clients (admin)
// ---------------------------------------------------------------------------
export function getClients() {
  return apiFetch<{
    items: { id: string; name: string; email: string; status: string }[];
    total: number;
  }>("/clients");
}

export function approveClient(id: string) {
  return apiFetch(`/clients/${id}/approve`, { method: "PATCH" });
}

export function rejectClient(id: string) {
  return apiFetch(`/clients/${id}/reject`, { method: "PATCH" });
}

// ---------------------------------------------------------------------------
// APIs (admin)
// ---------------------------------------------------------------------------
export function getApis() {
  return apiFetch<{
    items: {
      id: string;
      name: string;
      base_url: string;
      status: string;
      auth_type: string;
    }[];
    total: number;
  }>("/apis");
}

export function disableApi(id: string) {
  return apiFetch(`/apis/${id}/disable`, { method: "PATCH" });
}

// ---------------------------------------------------------------------------
// Permissions (admin)
// ---------------------------------------------------------------------------
export function grantPermission(clientId: string, apiId: string) {
  return apiFetch("/permissions", {
    method: "POST",
    body: JSON.stringify({ client_id: clientId, api_id: apiId }),
  });
}

export function revokePermission(clientId: string, apiId: string) {
  return apiFetch(`/permissions/${clientId}/${apiId}/revoke`, {
    method: "PATCH",
  });
}

// ---------------------------------------------------------------------------
// Catalog (client)
// ---------------------------------------------------------------------------
export function getCatalog() {
  return apiFetch<{ id: string; name: string; base_url: string; status: string }[]>(
    "/catalog"
  );
}

// ---------------------------------------------------------------------------
// Keys (client)
// ---------------------------------------------------------------------------
export function getKeys() {
  return apiFetch<{
    items: {
      id: string;
      name: string;
      key_prefix: string;
      status: string;
      created_at: string;
    }[];
    total: number;
  }>("/keys");
}

export function createKey(name: string) {
  return apiFetch<{
    id: string;
    name: string;
    key_prefix: string;
    secret: string;
    status: string;
    created_at: string;
  }>("/keys", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function revokeKey(id: string) {
  return apiFetch(`/keys/${id}/revoke`, { method: "PATCH" });
}

// ---------------------------------------------------------------------------
// Metrics (client dashboard + admin)
// ---------------------------------------------------------------------------
export function getClientDashboard(params?: {
  since?: string;
  until?: string;
}) {
  const qs = params
    ? "?" + new URLSearchParams(params as Record<string, string>).toString()
    : "";
  return apiFetch<{
    total_requests: number;
    error_rate: number;
    avg_latency_ms: number;
    total_cost: number;
    billable_requests: number;
    non_billable_requests: number;
  }>(`/metrics/dashboard${qs}`);
}

// ---------------------------------------------------------------------------
// Logs (client)
// ---------------------------------------------------------------------------
export function getLogs(skip = 0, limit = 20) {
  return apiFetch<{
    items: {
      correlation_id: string;
      path: string;
      method: string;
      status_code: number;
      latency_ms: number;
    }[];
    total: number;
  }>(`/logs?skip=${skip}&limit=${limit}`);
}
