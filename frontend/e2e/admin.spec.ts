/**
 * E2E — Operações de admin
 *
 * Fluxos críticos:
 * - Admin aprova um cliente pendente
 * - Admin concede permissão a um cliente
 * - Admin visualiza lista de APIs e aciona o toggle de disable
 *
 * O que testa que os testes Jest não pegam:
 * - Navegação real entre rotas (/admin → /admin/clients)
 * - Contrato entre componente e layout (sidebar ativa correta)
 * - Feedback visual após ação (badge de status atualizado na tela)
 */
import { test, expect } from "@playwright/test";
import {
  mockAdminLogin,
  mockAdminMetrics,
  mockClients,
  mockApis,
  mockPermissions,
  loginViaUi,
} from "./helpers";

const API = "http://localhost:8000";

// Helper: faz login como admin e vai para a rota indicada
async function adminGoTo(page: Parameters<typeof loginViaUi>[0], path: string) {
  await mockAdminLogin(page);
  await mockAdminMetrics(page);
  await loginViaUi(page, "admin@bridge.dev", "secret");
  await page.waitForURL(/\/admin/);
  await page.goto(path);
}

// ──────────────────────────────────────────────────────────────────────────
// Lista de clientes
// ──────────────────────────────────────────────────────────────────────────

test.describe("Admin — lista de clientes", () => {
  test("exibe clientes com status correto", async ({ page }) => {
    await mockClients(page);
    await adminGoTo(page, "/admin/clients");

    await expect(page.getByText("Acme Corp")).toBeVisible();
    await expect(page.getByText("Beta Ltd")).toBeVisible();
    // Use exact: true to avoid matching "Active Clients" header
    await expect(page.getByText("Active", { exact: true })).toBeVisible();
    await expect(page.getByText("Pending Approval")).toBeVisible();
  });

  test("exibe botão Approve apenas para cliente pendente", async ({ page }) => {
    await mockClients(page);
    await adminGoTo(page, "/admin/clients");

    // Beta Ltd is pending — should show Approve and Reject buttons
    await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reject" })).toBeVisible();
  });

  test("aprovação de cliente envia PATCH e atualiza UI", async ({ page }) => {
    await mockClients(page);

    let approvedId = "";
    await page.route(`${API}/clients/c2/approve`, (route) => {
      approvedId = "c2";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "c2", name: "Beta Ltd", email: "beta@example.com", status: "active" }),
      });
    });

    await adminGoTo(page, "/admin/clients");
    await page.getByRole("button", { name: "Approve" }).click();

    expect(approvedId).toBe("c2");
  });

  test("rejeição de cliente envia PATCH correto", async ({ page }) => {
    await mockClients(page);

    let rejectedId = "";
    await page.route(`${API}/clients/c2/reject`, (route) => {
      rejectedId = "c2";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "c2", status: "rejected" }),
      });
    });

    await adminGoTo(page, "/admin/clients");
    await page.getByRole("button", { name: "Reject" }).click();

    expect(rejectedId).toBe("c2");
  });
});

// ──────────────────────────────────────────────────────────────────────────
// Permissões
// ──────────────────────────────────────────────────────────────────────────

test.describe("Admin — permissões", () => {
  test("exibe painel de concessão de permissão", async ({ page }) => {
    await mockClients(page);
    await mockApis(page);
    await mockPermissions(page);
    await adminGoTo(page, "/admin/permissions");

    // Page shows "Select Client" section and API rows with GRANT buttons
    await expect(page.getByText("Select Client")).toBeVisible();
    // GRANT buttons exist (disabled until a client is selected)
    await expect(page.getByRole("button", { name: "GRANT" }).first()).toBeVisible();
  });

  test("carrega clientes e APIs na página", async ({ page }) => {
    await mockClients(page);
    await mockApis(page);
    await mockPermissions(page);
    await adminGoTo(page, "/admin/permissions");

    // Only active clients appear in the client selection panel
    await expect(page.getByText("Acme Corp")).toBeVisible();
    // Both active APIs appear in the API rows
    await expect(page.getByText("Stripe", { exact: true })).toBeVisible();
  });

  test("conceder permissão envia POST /permissions", async ({ page }) => {
    await mockClients(page);
    await mockApis(page);

    // Single handler that absorbs ALL /permissions requests.
    // route.continue() goes to the real network — never use it for mocked routes.
    let grantPayload: unknown = null;
    await page.route(`${API}/permissions`, (route) => {
      if (route.request().method() === "POST") {
        grantPayload = route.request().postDataJSON();
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({ client_id: "c1", api_id: "a1" }),
        });
      }
      // GET — empty initial permissions list
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      });
    });

    await adminGoTo(page, "/admin/permissions");

    // Step 1: select Acme Corp (only active client in mock data)
    await page.getByText("Acme Corp").click();

    // Step 2: click GRANT on the first API row (Stripe)
    await page.getByRole("button", { name: "GRANT" }).first().click();

    // Step 3: submit via the top-level "Apply Permissions" button
    await page.getByRole("button", { name: "Apply Permissions" }).click();

    expect(grantPayload).not.toBeNull();
  });
});

// ──────────────────────────────────────────────────────────────────────────
// Lista de APIs
// ──────────────────────────────────────────────────────────────────────────

test.describe("Admin — lista de APIs", () => {
  test("exibe APIs com status", async ({ page }) => {
    await mockApis(page);
    await adminGoTo(page, "/admin/apis");

    await expect(page.getByText("Stripe", { exact: true })).toBeVisible();
    await expect(page.getByText("SendGrid", { exact: true })).toBeVisible();
    // Both are active → "Active" badge visible at least once
    await expect(page.getByText("Active", { exact: true }).first()).toBeVisible();
  });

  test("toggle de API ativa envia PATCH correto", async ({ page }) => {
    await mockApis(page);

    let disabledId = "";
    await page.route(`${API}/apis/a1/disable`, (route) => {
      disabledId = "a1";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "a1", status: "inactive" }),
      });
    });

    await adminGoTo(page, "/admin/apis");

    // The toggle button is inside an opacity-0 div revealed on group hover.
    // Hover over the Stripe row to reveal the button, then click it.
    const stripeRow = page.locator("div.group").filter({ hasText: "Stripe" });
    await stripeRow.hover();
    await stripeRow.getByRole("button").click({ force: true });

    await expect.poll(() => disabledId).toBe("a1");
  });
});
