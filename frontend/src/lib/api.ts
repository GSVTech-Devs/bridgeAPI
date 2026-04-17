import { clearAuth } from "@/lib/auth";

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
    if (res.status === 401 && typeof window !== "undefined" && token) {
      clearAuth();
      window.location.href = "/login";
    }
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail ?? "Request failed");
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth  →  /auth/*
// ---------------------------------------------------------------------------
export function login(email: string, password: string) {
  return apiFetch<{ access_token: string; token_type: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe() {
  return apiFetch<{ email: string; role: string }>("/auth/me");
}

// ---------------------------------------------------------------------------
// Client auth  →  /clients/register  /clients/login
// ---------------------------------------------------------------------------
export function registerClient(data: { name: string; email: string; password: string }) {
  return apiFetch<{ id: string; name: string; email: string; status: string }>(
    "/clients/register",
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function clientLogin(email: string, password: string) {
  return apiFetch<{ access_token: string; token_type: string }>("/clients/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// ---------------------------------------------------------------------------
// Clients (admin)  →  /clients/*
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
// APIs (admin)  →  /apis/*
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

export function createApi(data: {
  name: string;
  slug?: string;
  base_url: string;
  url_template?: string;
  auth_type: string;
  master_key: string;
  description?: string;
}) {
  return apiFetch<{ id: string; name: string; slug?: string; base_url: string; url_template?: string; status: string; auth_type: string }>(
    "/apis",
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function enableApi(id: string) {
  return apiFetch(`/apis/${id}/enable`, { method: "PATCH" });
}

export function disableApi(id: string) {
  return apiFetch(`/apis/${id}/disable`, { method: "PATCH" });
}

export function getPermissions() {
  return apiFetch<{
    items: { client_id: string; api_id: string; client_name: string; api_name: string; status: string }[];
    total: number;
  }>("/permissions");
}

export function getAdminMetrics(params?: { since?: string; until?: string }) {
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
  }>(`/metrics/admin${qs}`);
}

// ---------------------------------------------------------------------------
// Permissions (admin)  →  /permissions/*
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
// Catalog (client)  →  /catalog
// ---------------------------------------------------------------------------
export function getCatalog() {
  return apiFetch<{
    items: {
      id: string;
      name: string;
      slug?: string;
      base_url: string;
      url_template?: string;
      status: string;
    }[];
    total: number;
  }>("/catalog");
}

// ---------------------------------------------------------------------------
// Keys (client)  →  /keys/*
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
// Metrics  →  /metrics/*
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
// Logs (client)  →  /logs
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
