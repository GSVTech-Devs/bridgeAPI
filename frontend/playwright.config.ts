import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config.
 *
 * Os testes usam page.route() para interceptar chamadas ao backend
 * (http://localhost:8000), portanto o backend NÃO precisa estar rodando.
 * Apenas o Next.js é iniciado automaticamente via webServer.
 *
 * Para rodar:
 *   cd frontend
 *   npx playwright install --with-deps chromium   # primeira vez
 *   npm run test:e2e
 *
 * No CI, o backend real pode ser integrado passando USE_REAL_BACKEND=1:
 *   USE_REAL_BACKEND=1 npm run test:e2e
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,           // migrações/estado compartilhado → serial
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Tempo máximo por asserção
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
