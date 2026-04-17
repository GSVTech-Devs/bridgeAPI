import { type Page } from "@playwright/test";

const API = "http://localhost:8000";

/**
 * Gera um JWT fake mas decodificável pelo decodeJwtPayload do LoginForm.
 * O payload é base64url-encoded JSON, que atob() consegue ler após
 * a substituição de - por + e _ por /.
 */
export function makeJwt(payload: Record<string, unknown>): string {
  const enc = (obj: unknown): string => {
    const b64 = Buffer.from(JSON.stringify(obj)).toString("base64url");
    // Adiciona padding para compatibilidade com atob() no browser
    const pad = (4 - (b64.length % 4)) % 4;
    return b64 + "=".repeat(pad);
  };
  return `${enc({ alg: "HS256", typ: "JWT" })}.${enc(payload)}.fakesignature`;
}

export const ADMIN_JWT = makeJwt({ sub: "admin@bridge.dev", role: "admin" });
export const CLIENT_JWT = makeJwt({ sub: "acme@example.com", role: "client" });

// ──────────────────────────────────────────────────────────────────────────
// Mocks de rota reutilizáveis
// ──────────────────────────────────────────────────────────────────────────

/** Intercepta POST /auth/login devolvendo o token informado. */
export async function mockAdminLogin(page: Page): Promise<void> {
  await page.route(`${API}/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: ADMIN_JWT, token_type: "bearer" }),
    })
  );
}

export async function mockClientLogin(page: Page): Promise<void> {
  await page.route(`${API}/auth/login`, (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid credentials" }) })
  );
  await page.route(`${API}/clients/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: CLIENT_JWT, token_type: "bearer" }),
    })
  );
}

/** Intercepta GET /clients devolvendo 2 clientes (1 active, 1 pending). */
export async function mockClients(page: Page): Promise<void> {
  await page.route(`${API}/clients`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          { id: "c1", name: "Acme Corp", email: "acme@example.com", status: "active" },
          { id: "c2", name: "Beta Ltd", email: "beta@example.com", status: "pending" },
        ],
        total: 2,
      }),
    })
  );
}

/** Intercepta GET /apis devolvendo 2 APIs. */
export async function mockApis(page: Page): Promise<void> {
  await page.route(`${API}/apis`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          { id: "a1", name: "Stripe", base_url: "https://api.stripe.com", status: "active", auth_type: "bearer" },
          { id: "a2", name: "SendGrid", base_url: "https://api.sendgrid.com", status: "active", auth_type: "api_key" },
        ],
        total: 2,
      }),
    })
  );
}

/** Intercepta GET /keys devolvendo 1 chave ativa. */
export async function mockKeys(page: Page): Promise<void> {
  await page.route(`${API}/keys`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          { id: "k1", name: "prod-key", key_prefix: "brg_abc", status: "active", created_at: "2024-01-01T00:00:00Z" },
        ],
        total: 1,
      }),
    })
  );
}

/** Intercepta GET /metrics/dashboard (client) */
export async function mockClientMetrics(page: Page): Promise<void> {
  await page.route(`${API}/metrics/dashboard`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_requests: 1250,
        error_rate: 0.025,
        avg_latency_ms: 87.3,
        total_cost: 12.5,
        billable_requests: 1100,
        non_billable_requests: 150,
      }),
    })
  );
}

/** Intercepta GET /catalog (client) — retorna { items, total } como a API real */
export async function mockCatalog(page: Page): Promise<void> {
  await page.route(`${API}/catalog`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          { id: "a1", name: "Stripe", base_url: "https://api.stripe.com", status: "active" },
        ],
        total: 1,
      }),
    })
  );
}

/** Intercepta /permissions (admin) — lista vazia por padrão.
 *  Nota: absorve TODOS os métodos para evitar que route.continue() acerte
 *  a rede real. Testes que precisam interceptar POST devem registrar seu
 *  próprio handler (sem chamar mockPermissions).
 */
export async function mockPermissions(page: Page): Promise<void> {
  await page.route(`${API}/permissions`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0 }),
    })
  );
}

/** Intercepta GET /metrics/admin */
export async function mockAdminMetrics(page: Page): Promise<void> {
  await page.route(`${API}/metrics/admin`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_requests: 8400,
        error_rate: 0.012,
        avg_latency_ms: 64.0,
        total_cost: 87.5,
        billable_requests: 7800,
        non_billable_requests: 600,
      }),
    })
  );
}

/**
 * Executa o fluxo de login via UI: navega para /login, preenche o form
 * e aguarda o redirect. Assume que os mocks de rota já foram configurados.
 */
export async function loginViaUi(
  page: Page,
  email: string,
  password: string
): Promise<void> {
  await page.goto("/login");
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
}
