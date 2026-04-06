import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import { apiFetch, login } from "../../src/lib/api";

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
});

describe("login", () => {
  it("returns access_token on success", async () => {
    const result = await login("admin@bridge.dev", "secret");
    expect(result.access_token).toBe("mock-token");
  });

  it("throws on invalid credentials", async () => {
    server.use(
      http.post(`${BASE}/login`, () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
      )
    );
    await expect(login("bad@email.com", "wrong")).rejects.toThrow(
      "Invalid credentials"
    );
  });
});
