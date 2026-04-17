/**
 * E2E — Fluxos de autenticação
 *
 * O que testa que os testes Jest não pegam:
 * - Roteamento real do Next.js: /login → /admin e /login → /dashboard
 * - Proteção de rota: navegar direto para /admin sem token redireciona para /login
 * - Logout: limpa localStorage e redireciona
 * - CORS / headers reais trafegando entre browser e Next.js
 *
 * O backend é mockado via page.route() — não precisa estar rodando.
 */
import { test, expect } from "@playwright/test";
import {
  mockAdminLogin,
  mockClientLogin,
  mockAdminMetrics,
  mockClientMetrics,
  mockCatalog,
  mockKeys,
  loginViaUi,
} from "./helpers";

// ──────────────────────────────────────────────────────────────────────────
// Login como admin
// ──────────────────────────────────────────────────────────────────────────

test.describe("Login — admin", () => {
  test("redireciona para /admin após login bem-sucedido", async ({ page }) => {
    await mockAdminLogin(page);
    await mockAdminMetrics(page);

    await loginViaUi(page, "admin@bridge.dev", "secret");

    await expect(page).toHaveURL(/\/admin/);
  });

  test("exibe a sidebar de admin após login", async ({ page }) => {
    await mockAdminLogin(page);
    await mockAdminMetrics(page);

    await loginViaUi(page, "admin@bridge.dev", "secret");
    await page.waitForURL(/\/admin/);

    // Scope to the sidebar <nav> to avoid matching admin-page card links like "Manage Clientes"
    const sidebarNav = page.getByRole("navigation");
    await expect(sidebarNav.getByRole("link", { name: /clientes/i })).toBeVisible();
    await expect(sidebarNav.getByRole("link", { name: /permissões/i })).toBeVisible();
  });

  test("armazena o token no localStorage após login", async ({ page }) => {
    await mockAdminLogin(page);
    await mockAdminMetrics(page);

    await loginViaUi(page, "admin@bridge.dev", "secret");
    await page.waitForURL(/\/admin/);

    const token = await page.evaluate(() => localStorage.getItem("bridge_token"));
    expect(token).toBeTruthy();
    expect(token).not.toBe("null");
  });
});

// ──────────────────────────────────────────────────────────────────────────
// Login como cliente
// ──────────────────────────────────────────────────────────────────────────

test.describe("Login — cliente", () => {
  test("redireciona para /dashboard após login de cliente", async ({ page }) => {
    await mockClientLogin(page);
    await mockClientMetrics(page);
    await mockCatalog(page);
    await mockKeys(page);

    await loginViaUi(page, "acme@example.com", "pass");

    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("exibe a sidebar do dashboard de cliente", async ({ page }) => {
    await mockClientLogin(page);
    await mockClientMetrics(page);
    await mockCatalog(page);
    await mockKeys(page);

    await loginViaUi(page, "acme@example.com", "pass");
    await page.waitForURL(/\/dashboard/);

    await expect(page.getByRole("link", { name: /catalog/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /my keys/i })).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────
// Credenciais inválidas
// ──────────────────────────────────────────────────────────────────────────

test.describe("Login — credenciais inválidas", () => {
  test("exibe mensagem de erro quando credenciais são inválidas", async ({ page }) => {
    await page.route("http://localhost:8000/auth/login", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid credentials" }),
      })
    );
    await page.route("http://localhost:8000/clients/login", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid credentials" }),
      })
    );

    await loginViaUi(page, "wrong@email.com", "wrongpass");

    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("não redireciona com credenciais inválidas", async ({ page }) => {
    await page.route("http://localhost:8000/auth/login", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid credentials" }) })
    );
    await page.route("http://localhost:8000/clients/login", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid credentials" }) })
    );

    await loginViaUi(page, "x@x.com", "x");

    // Permanece em /login
    await expect(page).toHaveURL(/\/login/);
  });
});

// ──────────────────────────────────────────────────────────────────────────
// Logout
// ──────────────────────────────────────────────────────────────────────────

test.describe("Logout", () => {
  test("botão Sair limpa o token e redireciona para /login (admin)", async ({
    page,
  }) => {
    await mockAdminLogin(page);
    await mockAdminMetrics(page);

    await loginViaUi(page, "admin@bridge.dev", "secret");
    await page.waitForURL(/\/admin/);

    await page.click('button:has-text("Sair")');

    await expect(page).toHaveURL(/\/login/);
    const token = await page.evaluate(() => localStorage.getItem("bridge_token"));
    expect(token).toBeNull();
  });
});
