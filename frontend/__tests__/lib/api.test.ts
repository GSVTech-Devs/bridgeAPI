import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import { apiFetch, login } from "../../src/lib/api";
import { clearAuth } from "../../src/lib/auth";

const BASE = "http://localhost:8000";

describe("apiFetch", () => {
  it("calls the correct URL", async () => {
    server.use(
      http.get(`${BASE}/health`, () => HttpResponse.json({ status: "ok" }))
    );
    const result = await apiFetch<{ status: string }>("/health");
    expect(result.status).toBe("ok");
  });

  it("attaches Bearer token from localStorage when present", async () => {
    let capturedAuth = "";
    server.use(
      http.get(`${BASE}/me`, ({ request }) => {
        capturedAuth = request.headers.get("authorization") ?? "";
        return HttpResponse.json({ email: "admin@bridge.dev", role: "admin" });
      })
    );
    localStorage.setItem("bridge_token", "test-jwt");
    await apiFetch("/me");
    expect(capturedAuth).toBe("Bearer test-jwt");
    localStorage.removeItem("bridge_token");
  });

  it("does not attach Authorization when no token in localStorage", async () => {
    let capturedAuth: string | null = "initial";
    server.use(
      http.get(`${BASE}/me`, ({ request }) => {
        capturedAuth = request.headers.get("authorization");
        return HttpResponse.json({ email: "x", role: "admin" });
      })
    );
    localStorage.removeItem("bridge_token");
    await apiFetch("/me");
    expect(capturedAuth).toBeNull();
  });

  it("throws an Error with detail message on non-ok response", async () => {
    server.use(
      http.post(`${BASE}/login`, () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
      )
    );
    await expect(
      apiFetch("/login", { method: "POST", body: JSON.stringify({}) })
    ).rejects.toThrow("Invalid credentials");
  });

  describe("401 with existing token (expired session)", () => {
    const originalLocation = window.location;

    beforeEach(() => {
      Object.defineProperty(window, "location", {
        value: { href: "" },
        writable: true,
        configurable: true,
      });
    });

    afterEach(() => {
      server.resetHandlers();
      Object.defineProperty(window, "location", {
        value: originalLocation,
        writable: true,
        configurable: true,
      });
      localStorage.removeItem("bridge_token");
      localStorage.removeItem("bridge_role");
    });

    it("clears auth and redirects to /login when 401 with token present", async () => {
      localStorage.setItem("bridge_token", "expired-token");
      localStorage.setItem("bridge_role", "admin");
      server.use(
        http.get(`${BASE}/protected`, () =>
          HttpResponse.json({ detail: "Not authenticated" }, { status: 401 })
        )
      );
      await apiFetch("/protected").catch(() => {});
      expect(localStorage.getItem("bridge_token")).toBeNull();
      expect(window.location.href).toBe("/login");
    });

    it("does not redirect to /login on 401 when no token (wrong credentials)", async () => {
      localStorage.removeItem("bridge_token");
      server.use(
        http.post(`${BASE}/auth/login`, () =>
          HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
        )
      );
      await apiFetch("/auth/login", { method: "POST" }).catch(() => {});
      expect(window.location.href).not.toBe("/login");
    });
  });
});

describe("login", () => {
  it("returns access_token on success", async () => {
    const result = await login("admin@bridge.dev", "secret");
    expect(result.access_token).toBe("mock-token");
  });

  it("throws on invalid credentials", async () => {
    server.use(
      http.post(`${BASE}/auth/login`, () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
      )
    );
    await expect(login("bad@email.com", "wrong")).rejects.toThrow(
      "Invalid credentials"
    );
  });
});
