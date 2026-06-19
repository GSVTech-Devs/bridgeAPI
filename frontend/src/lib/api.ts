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

  if (res.status === 204) {
    return undefined as T;
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
  return apiFetch<{
    email: string;
    role: string;
    account_id?: string | null;
  }>("/auth/me");
}

// Login do portal (usuários de account: responsável/membro).
export function portalLogin(email: string, password: string) {
  return apiFetch<{ access_token: string; token_type: string }>(
    "/auth/portal/login",
    { method: "POST", body: JSON.stringify({ email, password }) }
  );
}

// Troca de senha self-service do usuário do portal (não altera o email).
export function changePassword(data: {
  current_password: string;
  new_password: string;
}) {
  return apiFetch<void>("/auth/portal/password", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Accounts (admin)  →  /admin/*
// ---------------------------------------------------------------------------
export type AccountType = "individual" | "company";

export function getAccounts() {
  return apiFetch<{
    items: {
      id: string;
      name: string;
      type: AccountType;
      status: string;
      created_at: string;
      owner_email: string | null;
      owner_id: string | null;
    }[];
    total: number;
  }>("/admin/accounts");
}

// Cria um usuário avulso (account individual + responsável).
export function createIndividualUser(data: {
  name: string;
  email: string;
  password: string;
}) {
  return apiFetch<{
    account: { id: string; name: string; type: AccountType; status: string };
    owner_email: string;
    owner_id: string;
  }>("/admin/users", { method: "POST", body: JSON.stringify(data) });
}

// Cria uma empresa + usuário responsável inicial.
export function createCompany(data: {
  company_name: string;
  owner_email: string;
  owner_password: string;
}) {
  return apiFetch<{
    account: { id: string; name: string; type: AccountType; status: string };
    owner_email: string;
    owner_id: string;
  }>("/admin/companies", { method: "POST", body: JSON.stringify(data) });
}

// Troca o email e/ou a senha de acesso do responsável da conta
// (vale tanto para empresas quanto para usuários avulsos).
export function updateAccountCredentials(
  id: string,
  data: { email?: string; password?: string }
) {
  return apiFetch<{
    account_id: string;
    owner_id: string;
    owner_email: string;
  }>(`/admin/accounts/${id}/credentials`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function blockAccount(id: string) {
  return apiFetch(`/admin/accounts/${id}/block`, { method: "PATCH" });
}

export function unblockAccount(id: string) {
  return apiFetch(`/admin/accounts/${id}/unblock`, { method: "PATCH" });
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
  cost_per_query?: number;
  description?: string;
}) {
  return apiFetch<{ id: string; name: string; slug?: string; base_url: string; url_template?: string; status: string; auth_type: string; cost_per_query?: number }>(
    "/apis",
    { method: "POST", body: JSON.stringify(data) }
  );
}

export function updateApi(id: string, data: {
  name?: string;
  slug?: string;
  base_url?: string;
  url_template?: string;
  auth_type?: string;
  master_key?: string;
  cost_per_query?: number;
}) {
  return apiFetch<{ id: string; name: string; slug?: string; base_url: string; url_template?: string; status: string; auth_type: string; cost_per_query?: number }>(
    `/apis/${id}`,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export function enableApi(id: string) {
  return apiFetch(`/apis/${id}/enable`, { method: "PATCH" });
}

export function disableApi(id: string) {
  return apiFetch(`/apis/${id}/disable`, { method: "PATCH" });
}

export function deleteApi(id: string) {
  return apiFetch(`/apis/${id}`, { method: "DELETE" });
}

export function getPermissions() {
  return apiFetch<{
    items: { account_id: string; api_id: string; account_name: string; api_name: string; status: string }[];
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

export function getAdminClientsSummary(params?: { since?: string; until?: string }) {
  const qs = params
    ? "?" + new URLSearchParams(params as Record<string, string>).toString()
    : "";
  return apiFetch<{
    items: {
      client_id: string;
      client_name: string;
      client_email: string;
      total_requests: number;
      error_count: number;
      success_count: number;
      total_cost: number;
    }[];
  }>(`/metrics/admin/clients/summary${qs}`);
}

export function getAdminClientDetail(clientId: string, params?: { since?: string; until?: string }) {
  const qs = params
    ? "?" + new URLSearchParams(params as Record<string, string>).toString()
    : "";
  return apiFetch<{
    client_id: string;
    total_cost: number;
    total_requests: number;
    items: {
      api_id: string;
      api_name: string;
      total_requests: number;
      error_count: number;
      success_count: number;
      total_cost: number;
    }[];
  }>(`/metrics/admin/clients/${clientId}${qs}`);
}

export function getAdminUsage(params?: { since?: string; until?: string }) {
  const qs = params
    ? "?" + new URLSearchParams(params as Record<string, string>).toString()
    : "";
  return apiFetch<{
    items: {
      client_id: string;
      client_name: string;
      client_email: string;
      api_id: string;
      api_name: string;
      total_requests: number;
      total_cost: number;
    }[];
  }>(`/metrics/admin/usage${qs}`);
}

export function getAdminMetricsBreakdown(params?: { since?: string; until?: string }) {
  const qs = params
    ? "?" + new URLSearchParams(params as Record<string, string>).toString()
    : "";
  return apiFetch<{
    items: { api_id: string; api_name: string; total_requests: number; error_rate: number }[];
  }>(`/metrics/admin/breakdown${qs}`);
}

export function getAdminLogs(skip = 0, limit = 10) {
  return apiFetch<{
    items: {
      correlation_id: string;
      client_id: string;
      api_id: string;
      path: string;
      method: string;
      status_code: number;
      latency_ms: number;
      created_at: string | null;
    }[];
    total: number;
  }>(`/logs/admin?skip=${skip}&limit=${limit}`);
}

export function getAdminErrorLogs(params?: { api_id?: string; skip?: number; limit?: number }) {
  const qs = params
    ? "?" + new URLSearchParams(
        Object.fromEntries(
          Object.entries({ skip: "0", limit: "100", ...params }).filter(([, v]) => v !== undefined)
        ) as Record<string, string>
      ).toString()
    : "";
  return apiFetch<{
    items: {
      correlation_id: string;
      client_id: string;
      api_id: string;
      key_id: string;
      path: string;
      method: string;
      status_code: number;
      latency_ms: number;
      request_body: string | null;
      response_body: string | null;
      created_at: string | null;
    }[];
    total: number;
  }>(`/logs/admin/errors${qs}`);
}

// ---------------------------------------------------------------------------
// Permissions (admin)  →  /permissions/*
// ---------------------------------------------------------------------------
export function grantPermission(accountId: string, apiId: string) {
  return apiFetch("/permissions", {
    method: "POST",
    body: JSON.stringify({ account_id: accountId, api_id: apiId }),
  });
}

export function revokePermission(accountId: string, apiId: string) {
  return apiFetch(`/permissions/${accountId}/${apiId}/revoke`, {
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
      api_id: string | null;
      name: string;
      key_prefix: string;
      api_key: string | null;
      status: string;
      created_at: string;
    }[];
    total: number;
  }>("/keys");
}

export function createKey(name: string, apiId: string) {
  return apiFetch<{
    id: string;
    api_id: string;
    name: string;
    key_prefix: string;
    api_key: string;
    status: string;
    created_at: string;
  }>("/keys", {
    method: "POST",
    body: JSON.stringify({ name, api_id: apiId }),
  });
}

export function revokeKey(id: string) {
  return apiFetch(`/keys/${id}/revoke`, { method: "PATCH" });
}

// ---------------------------------------------------------------------------
// Metrics  →  /metrics/*
// ---------------------------------------------------------------------------
function buildQS(params: Record<string, string | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) qs.set(k, v);
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export function getClientByKey(params?: { api_id?: string; since?: string; until?: string }) {
  return apiFetch<{
    items: {
      key_id: string;
      key_name: string;
      key_prefix: string;
      total_requests: number;
    }[];
  }>(`/metrics/client/by-key${params ? buildQS(params) : ""}`);
}

export function getClientByApi(params?: { since?: string; until?: string }) {
  const qs = params ? buildQS(params) : "";
  return apiFetch<{
    items: {
      api_id: string;
      api_name: string;
      total_requests: number;
      error_count: number;
      success_count: number;
      total_cost: number;
    }[];
  }>(`/metrics/client/by-api${qs}`);
}

export function getClientStatusCodes(params?: { since?: string; until?: string }) {
  const qs = params
    ? "?" + new URLSearchParams(params as Record<string, string>).toString()
    : "";
  return apiFetch<{
    items: {
      api_id: string;
      api_name: string;
      status_code: number;
      count: number;
    }[];
  }>(`/metrics/client/status-codes${qs}`);
}

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
export function getLogs(skip = 0, limit = 20, api_id?: string, since?: string, until?: string) {
  const qs = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (api_id) qs.set("api_id", api_id);
  if (since) qs.set("since", since);
  if (until) qs.set("until", until);
  return apiFetch<{
    items: {
      correlation_id: string;
      api_id: string;
      key_id: string;
      key_name: string | null;
      path: string;
      method: string;
      status_code: number;
      latency_ms: number;
      response_body: string | null;
      created_at: string | null;
    }[];
    total: number;
  }>(`/logs?${qs}`);
}
