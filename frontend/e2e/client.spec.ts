/**
 * E2E — Operações de cliente (caminho feliz)
 *
 * Fluxos críticos:
 * - Cliente gera uma API key e vê o segredo completo na tela
 * - Cliente revoga uma chave
 * - Cliente visualiza o catálogo de APIs autorizadas
 *
 * O que testa que os testes Jest não pegam:
 * - Roteamento Next.js: /dashboard/keys, /dashboard/catalog
 * - O segredo da chave aparece UMA VEZ após criação (estado React temporário)
 * - Fluxo ponta-a-ponta: login → dashboard → gerar chave → ver segredo
 *
 * NOTA sobre mocking: route.continue() encaminha para a rede real (não ao
 * próximo handler). Testes que interceptam POST /keys não devem usar
 * clientGoTo (que registra mockKeys para todos os métodos) — em vez disso
 * registram um handler único que trata GET e POST.
 */
import { test, expect } from "@playwright/test";
import {
  mockClientLogin,
  mockClientMetrics,
  mockCatalog,
  mockKeys,
  loginViaUi,
} from "./helpers";

const API = "http://localhost:8000";

/** Dados de uma chave existente ativa. */
const EXISTING_KEY = {
  id: "k1",
  name: "prod-key",
  key_prefix: "brg_abc",
  status: "active",
  created_at: "2024-01-01T00:00:00Z",
};

// Helper: login como cliente e navega para a rota indicada
async function clientGoTo(page: Parameters<typeof loginViaUi>[0], path: string) {
  await mockClientLogin(page);
  await mockClientMetrics(page);
  await mockCatalog(page);
  await mockKeys(page);
  await loginViaUi(page, "acme@example.com", "pass");
  await page.waitForURL(/\/dashboard/);
  await page.goto(path);
}

// ──────────────────────────────────────────────────────────────────────────
// Dashboard principal
// ──────────────────────────────────────────────────────────────────────────

test.describe("Cliente — dashboard", () => {
  test("exibe métricas após login", async ({ page }) => {
    await mockClientLogin(page);
    await mockClientMetrics(page);
    await mockCatalog(page);
    await mockKeys(page);

    await loginViaUi(page, "acme@example.com", "pass");
    await page.waitForURL(/\/dashboard/);

    // total_requests: 1250 — toLocaleString() may render as "1,250" or "1.250"
    await expect(page.getByText(/1[,.]250/)).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────
// API Keys
// ──────────────────────────────────────────────────────────────────────────

test.describe("Cliente — API keys", () => {
  test("exibe chave existente com prefixo", async ({ page }) => {
    await clientGoTo(page, "/dashboard/keys");

    await expect(page.getByText(/brg_abc/)).toBeVisible();
  });

  test("gerar chave: POST /keys e exibe segredo completo", async ({ page }) => {
    // Não usa clientGoTo: registramos um handler único para /keys que trata
    // GET e POST. Se usássemos clientGoTo, mockKeys (registrado por último)
    // ficaria como handler LIFO primário e interceptaria também o POST.
    await mockClientLogin(page);
    await mockClientMetrics(page);
    await mockCatalog(page);

    await page.route(`${API}/keys`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "k2",
            name: "new-key",
            key_prefix: "brg_xyz",
            secret: "brg_xyz_full-secret",
            status: "active",
            created_at: "2024-06-01T00:00:00Z",
          }),
        });
      }
      // GET /keys — lista existente
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [EXISTING_KEY], total: 1 }),
      });
    });

    await loginViaUi(page, "acme@example.com", "pass");
    await page.waitForURL(/\/dashboard/);
    await page.goto("/dashboard/keys");

    // KeysPage requires a name before the submit button is enabled
    await page.fill('input[placeholder*="Nome"]', "test-key");
    await page.getByRole("button", { name: /gerar nova chave/i }).click();

    // Secret appears once after creation
    await expect(page.getByText("brg_xyz_full-secret")).toBeVisible();
  });

  test("revogar chave: PATCH /keys/:id/revoke", async ({ page }) => {
    let revokedId = "";
    await page.route(`${API}/keys/k1/revoke`, (route) => {
      revokedId = "k1";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "k1", status: "revoked" }),
      });
    });

    await clientGoTo(page, "/dashboard/keys");

    // Revoke button has title="Revoke Key" (icon-only, always visible)
    await page.click('[title="Revoke Key"]');

    expect(revokedId).toBe("k1");
  });

  test("exibe status da chave", async ({ page }) => {
    await clientGoTo(page, "/dashboard/keys");

    // Active key shows "Active" badge
    await expect(page.getByText("Active")).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────
// Catálogo de APIs
// ──────────────────────────────────────────────────────────────────────────

test.describe("Cliente — catálogo", () => {
  test("exibe APIs autorizadas", async ({ page }) => {
    await clientGoTo(page, "/dashboard/catalog");

    // Use role heading to avoid strict-mode violation from partial text matches
    await expect(page.getByRole("heading", { name: "Stripe" })).toBeVisible();
    await expect(page.getByText(/api\.stripe\.com/i)).toBeVisible();
  });

  test("exibe status da API no catálogo", async ({ page }) => {
    await clientGoTo(page, "/dashboard/catalog");

    // CatalogPage renders "Operational" for active APIs (not the raw "active" value)
    await expect(page.getByText("Operational")).toBeVisible();
  });

  test("exibe estado vazio quando nenhuma API está autorizada", async ({ page }) => {
    // Set up mocks manually to control /catalog without conflict from mockCatalog
    await mockClientLogin(page);
    await mockClientMetrics(page);
    await mockKeys(page);

    // Empty catalog — must return { items, total } format that getCatalog() expects
    await page.route(`${API}/catalog`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      })
    );

    await loginViaUi(page, "acme@example.com", "pass");
    await page.waitForURL(/\/dashboard/);
    await page.goto("/dashboard/catalog");

    await expect(page.getByText(/nenhuma api/i)).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────
// Fluxo completo: login → gerar chave → ver no dashboard
// ──────────────────────────────────────────────────────────────────────────

test.describe("Fluxo completo — gerar chave", () => {
  test("login → /dashboard/keys → criar chave → ver segredo", async ({ page }) => {
    await mockClientLogin(page);
    await mockClientMetrics(page);
    await mockCatalog(page);

    // Single handler: GET returns empty list, POST creates new key
    await page.route(`${API}/keys`, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "k_new",
            name: "minha-chave",
            key_prefix: "brg_e2e",
            secret: "brg_e2e_supersecret",
            status: "active",
            created_at: new Date().toISOString(),
          }),
        });
      }
      // GET /keys — empty for simplicity
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      });
    });

    // 1. Login
    await loginViaUi(page, "acme@example.com", "pass");
    await page.waitForURL(/\/dashboard/);

    // 2. Navega para keys
    await page.goto("/dashboard/keys");

    // 3. Preenche o nome e cria a chave
    await page.fill('input[placeholder*="Nome"]', "minha-chave");
    await page.getByRole("button", { name: /gerar nova chave/i }).click();

    // 4. Segredo aparece na tela
    await expect(page.getByText("brg_e2e_supersecret")).toBeVisible();
  });
});
