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

  // Em uploads (FormData) deixamos o browser definir o Content-Type com o
  // boundary correto; forçar application/json quebraria o multipart.
  const isFormData =
    typeof FormData !== "undefined" && options?.body instanceof FormData;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
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
    capabilities: string[];
    account_type?: string | null;
    account_name?: string | null;
    is_owner: boolean;
    account_count: number;
  }>("/auth/me");
}

// Uma empresa/account acessível pelo email logado (para o seletor de empresa).
export type CompanyOption = {
  account_id: string;
  name: string;
  type: AccountType;
  role: string;
};

// Login do portal: devolve um token de identidade + a lista de empresas
// acessíveis. A empresa é escolhida em seguida via selectCompany().
export function portalLogin(email: string, password: string) {
  return apiFetch<{
    access_token: string;
    token_type: string;
    companies: CompanyOption[];
  }>("/auth/portal/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// Empresas que o usuário logado pode acessar (seleção pós-login / troca).
export function getPortalCompanies() {
  return apiFetch<{ companies: CompanyOption[] }>("/auth/portal/companies");
}

// Emite o token escopado à empresa escolhida (sem reentrar a senha).
export function selectCompany(accountId: string) {
  return apiFetch<{ access_token: string; token_type: string }>(
    "/auth/portal/select",
    { method: "POST", body: JSON.stringify({ account_id: accountId }) }
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
// Branding (portal)  →  /portal/branding
// ---------------------------------------------------------------------------
export type BrandModeColors = {
  primary: string | null;
  secondary: string | null;
  tertiary: string | null;
  background: string | null;
};

export type Branding = {
  logo_data_uri: string | null;
  brand_theme: { light: BrandModeColors; dark: BrandModeColors } | null;
};

export function getBranding() {
  return apiFetch<Branding>("/portal/branding");
}

// Upload/substitui a logo da conta (owner). Validado também no backend.
export function uploadLogo(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<Branding>("/portal/branding/logo", {
    method: "PUT",
    body: form,
  });
}

// Remove a logo, voltando à marca padrão (owner).
export function deleteLogo() {
  return apiFetch<Branding>("/portal/branding/logo", {
    method: "DELETE",
  });
}

// Define o tema de marca da conta (owner). Cores hex #RRGGBB por modo;
// cada slot é opcional (omitido/null = cor padrão). Validado no backend.
export function updateBrandTheme(theme: {
  light: Partial<BrandModeColors>;
  dark: Partial<BrandModeColors>;
}) {
  return apiFetch<Branding>("/portal/branding/colors", {
    method: "PUT",
    body: JSON.stringify(theme),
  });
}

// Remove o tema de marca, voltando ao tema padrão (owner).
export function deleteBrandTheme() {
  return apiFetch<Branding>("/portal/branding/colors", {
    method: "DELETE",
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
      proxy_pool_id?: string | null;
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
// Debug — logs estruturados das APIs e timeline por correlation_id
// ---------------------------------------------------------------------------
export type AppLogEntry = {
  correlation_id: string;
  api_id: string;
  level: string;
  event: string;
  message: string | null;
  timestamp: string | null;
  duration_ms: number | null;
  proxy_id: string | null;
  captcha_provider: string | null;
  error_code: string | null;
  api_version: string | null;
  sdk_version: string | null;
  extra: Record<string, unknown>;
  created_at: string | null;
};

export type TraceItem = {
  source: "gateway" | "app";
  correlation_id: string;
  timestamp: string | null;
  created_at: string | null;
  path: string | null;
  method: string | null;
  status_code: number | null;
  latency_ms: number | null;
  level: string | null;
  event: string | null;
  message: string | null;
  error_code: string | null;
  proxy_id: string | null;
  captcha_provider: string | null;
};

export function getAdminAppLogs(params?: {
  correlation_id?: string;
  api_id?: string;
  level?: string;
  event?: string;
  error_code?: string;
  since?: string;
  until?: string;
  skip?: number;
  limit?: number;
}) {
  const qs = params
    ? "?" + new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
        ) as Record<string, string>
      ).toString()
    : "";
  return apiFetch<{ items: AppLogEntry[]; total: number }>(`/logs/admin/app${qs}`);
}

export function getAdminTrace(correlationId: string) {
  return apiFetch<{ correlation_id: string; items: TraceItem[]; total: number }>(
    `/logs/admin/trace/${encodeURIComponent(correlationId)}`
  );
}

// ---------------------------------------------------------------------------
// Status / readiness das APIs  →  /status/*
// ---------------------------------------------------------------------------
export type StatusCheck = Record<string, unknown> & { status: string };

export type StatusOverviewItem = {
  api_id: string;
  api_name: string | null;
  status: string;            // healthy | degraded | down | unknown
  reported_status: string | null;
  sdk_version: string | null;
  uptime_s: number | null;
  checks: Record<string, StatusCheck>;
  last_seen: string | null;
  stale: boolean;
};

export type StatusEvent = {
  api_id: string;
  api_name: string | null;
  from_status: string;
  to_status: string;
  at: string | null;
};

export function getStatusOverview() {
  return apiFetch<{ items: StatusOverviewItem[]; total: number }>("/status/overview");
}

export function getStatusEvents(limit = 50) {
  return apiFetch<{ items: StatusEvent[]; total: number }>(
    `/status/events?limit=${limit}`
  );
}

// EventSource não envia o header Authorization — o token vai por query param.
export function statusStreamUrl(token: string) {
  return `${BASE_URL}/status/stream?token=${encodeURIComponent(token)}`;
}

// ---------------------------------------------------------------------------
// Proxies & pools  →  /proxies/*
// ---------------------------------------------------------------------------
export type ProxyPool = {
  id: string;
  account_id: string | null;
  name: string;
  description: string | null;
  proxy_count: number;
  created_at: string;
};

export type Proxy = {
  id: string;
  account_id: string | null;
  pool_id: string | null;
  name: string;
  provider: string | null;
  ownership: string;
  type: string;
  scheme: string;
  host: string;
  port: number;
  username: string | null;
  has_password: boolean;
  rotation: string;
  session_ttl_s: number | null;
  status: string;
  priority: number;
  last_error: string | null;
  last_error_at: string | null;
  created_at: string;
};

export type ProxyInput = {
  name: string;
  host: string;
  port: number;
  scheme?: string;
  type?: string;
  ownership?: string;
  provider?: string | null;
  username?: string | null;
  password?: string | null;
  rotation?: string;
  session_ttl_s?: number | null;
  priority?: number;
  pool_id?: string | null;
};

export function getProxyPools() {
  return apiFetch<{ items: ProxyPool[]; total: number }>("/proxies/pools");
}

export function createProxyPool(name: string, description?: string) {
  return apiFetch<ProxyPool>("/proxies/pools", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export function deleteProxyPool(poolId: string) {
  return apiFetch<void>(`/proxies/pools/${poolId}`, { method: "DELETE" });
}

export function getProxies(poolId?: string) {
  const qs = poolId ? `?pool_id=${poolId}` : "";
  return apiFetch<{ items: Proxy[]; total: number }>(`/proxies${qs}`);
}

export function createProxy(body: ProxyInput) {
  return apiFetch<Proxy>("/proxies", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateProxy(proxyId: string, body: Partial<ProxyInput> & { status?: string }) {
  return apiFetch<Proxy>(`/proxies/${proxyId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteProxy(proxyId: string) {
  return apiFetch<void>(`/proxies/${proxyId}`, { method: "DELETE" });
}

export function assignProxyPool(apiId: string, proxyPoolId: string | null) {
  return apiFetch<{ api_id: string; proxy_pool_id: string | null }>(
    `/proxies/assignments/${apiId}`,
    { method: "PUT", body: JSON.stringify({ proxy_pool_id: proxyPoolId }) }
  );
}

// ---------------------------------------------------------------------------
// Proxies do cliente (autosserviço)  →  /client/proxies/*
// Mesmos tipos do admin, mas escopados à conta do usuário logado.
// ---------------------------------------------------------------------------
export type ClientProxyAssignment = {
  api_id: string;
  api_name: string;
  proxy_pool_id: string | null;
};

export function getClientProxyPools() {
  return apiFetch<{ items: ProxyPool[]; total: number }>("/client/proxies/pools");
}

export function createClientProxyPool(name: string, description?: string) {
  return apiFetch<ProxyPool>("/client/proxies/pools", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export function deleteClientProxyPool(poolId: string) {
  return apiFetch<void>(`/client/proxies/pools/${poolId}`, { method: "DELETE" });
}

export function getClientProxies(poolId?: string) {
  const qs = poolId ? `?pool_id=${poolId}` : "";
  return apiFetch<{ items: Proxy[]; total: number }>(`/client/proxies${qs}`);
}

export function createClientProxy(body: ProxyInput) {
  return apiFetch<Proxy>("/client/proxies", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateClientProxy(
  proxyId: string,
  body: Partial<ProxyInput> & { status?: string }
) {
  return apiFetch<Proxy>(`/client/proxies/${proxyId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteClientProxy(proxyId: string) {
  return apiFetch<void>(`/client/proxies/${proxyId}`, { method: "DELETE" });
}

export function getClientProxyAssignments() {
  return apiFetch<{ items: ClientProxyAssignment[] }>(
    "/client/proxies/assignments"
  );
}

export function setClientProxyAssignment(
  apiId: string,
  proxyPoolId: string | null
) {
  return apiFetch<{ api_id: string; proxy_pool_id: string | null }>(
    `/client/proxies/assignments/${apiId}`,
    { method: "PUT", body: JSON.stringify({ proxy_pool_id: proxyPoolId }) }
  );
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

// ---------------------------------------------------------------------------
// Roles & Members (portal — owner de empresa)  →  /portal/*
// ---------------------------------------------------------------------------
export type Role = {
  id: string;
  name: string;
  capabilities: string[];
  member_count: number;
  created_at: string;
};

export type Member = {
  id: string;
  email: string;
  role_id: string | null;
  role_name: string | null;
  created_at: string;
};

export function getRoles() {
  return apiFetch<{ items: Role[] }>("/portal/roles");
}

export function createRole(data: { name: string; capabilities: string[] }) {
  return apiFetch<Role>("/portal/roles", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateRole(
  id: string,
  data: { name?: string; capabilities?: string[] }
) {
  return apiFetch<Role>(`/portal/roles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteRole(id: string) {
  return apiFetch<void>(`/portal/roles/${id}`, { method: "DELETE" });
}

export function getMembers() {
  return apiFetch<{ items: Member[] }>("/portal/members");
}

export function createMember(data: {
  email: string;
  password: string;
  role_id: string;
}) {
  return apiFetch<Member>("/portal/members", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateMember(
  id: string,
  data: { email?: string; password?: string; role_id?: string }
) {
  return apiFetch<Member>(`/portal/members/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteMember(id: string) {
  return apiFetch<void>(`/portal/members/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Roles & Members (admin — qualquer empresa)  →  /admin/accounts/{id}/*
// Espelham as funções do portal, mas escopadas por accountId na URL.
// ---------------------------------------------------------------------------
export function adminGetRoles(accountId: string) {
  return apiFetch<{ items: Role[] }>(`/admin/accounts/${accountId}/roles`);
}

export function adminCreateRole(
  accountId: string,
  data: { name: string; capabilities: string[] }
) {
  return apiFetch<Role>(`/admin/accounts/${accountId}/roles`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function adminUpdateRole(
  accountId: string,
  roleId: string,
  data: { name?: string; capabilities?: string[] }
) {
  return apiFetch<Role>(`/admin/accounts/${accountId}/roles/${roleId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function adminDeleteRole(accountId: string, roleId: string) {
  return apiFetch<void>(`/admin/accounts/${accountId}/roles/${roleId}`, {
    method: "DELETE",
  });
}

export function adminGetMembers(accountId: string) {
  return apiFetch<{ items: Member[] }>(`/admin/accounts/${accountId}/members`);
}

export function adminCreateMember(
  accountId: string,
  data: { email: string; password: string; role_id: string }
) {
  return apiFetch<Member>(`/admin/accounts/${accountId}/members`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function adminUpdateMember(
  accountId: string,
  memberId: string,
  data: { email?: string; password?: string; role_id?: string }
) {
  return apiFetch<Member>(`/admin/accounts/${accountId}/members/${memberId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function adminDeleteMember(accountId: string, memberId: string) {
  return apiFetch<void>(`/admin/accounts/${accountId}/members/${memberId}`, {
    method: "DELETE",
  });
}
