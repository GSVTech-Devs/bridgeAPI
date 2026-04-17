import { http, HttpResponse } from "msw";

const BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export const handlers = [
  http.post(`${BASE}/auth/login`, () =>
    HttpResponse.json({ access_token: "mock-token", token_type: "bearer" })
  ),

  http.get(`${BASE}/me`, () =>
    HttpResponse.json({ email: "admin@bridge.dev", role: "admin" })
  ),

  // ---------------------------------------------------------------------------
  // Clients (admin)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/clients`, () =>
    HttpResponse.json({
      items: [
        {
          id: "c1",
          name: "Acme Corp",
          email: "acme@example.com",
          status: "active",
        },
        {
          id: "c2",
          name: "Beta Ltd",
          email: "beta@example.com",
          status: "pending",
        },
      ],
      total: 2,
    })
  ),

  http.patch(`${BASE}/clients/:id/approve`, ({ params }) =>
    HttpResponse.json({ id: params.id, status: "active" })
  ),

  http.patch(`${BASE}/clients/:id/reject`, ({ params }) =>
    HttpResponse.json({ id: params.id, status: "rejected" })
  ),

  // ---------------------------------------------------------------------------
  // APIs (admin)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/apis`, () =>
    HttpResponse.json({
      items: [
        {
          id: "a1",
          name: "Stripe",
          base_url: "https://api.stripe.com",
          status: "active",
          auth_type: "bearer",
        },
        {
          id: "a2",
          name: "SendGrid",
          base_url: "https://api.sendgrid.com",
          status: "inactive",
          auth_type: "api_key",
        },
      ],
      total: 2,
    })
  ),

  http.patch(`${BASE}/apis/:id/disable`, ({ params }) =>
    HttpResponse.json({ id: params.id, status: "inactive" })
  ),

  // ---------------------------------------------------------------------------
  // Permissions (admin)
  // ---------------------------------------------------------------------------
  http.post(`${BASE}/permissions`, () =>
    HttpResponse.json({ client_id: "c1", api_id: "a1" }, { status: 201 })
  ),

  http.patch(`${BASE}/permissions/:clientId/:apiId/revoke`, ({ params }) =>
    HttpResponse.json({ client_id: params.clientId, api_id: params.apiId })
  ),

  // ---------------------------------------------------------------------------
  // Catalog (client)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/catalog`, () =>
    HttpResponse.json({
      items: [
        {
          id: "a1",
          name: "Stripe",
          base_url: "https://api.stripe.com",
          status: "active",
        },
      ],
      total: 1,
    })
  ),

  // ---------------------------------------------------------------------------
  // Permissions (admin) — GET list
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/permissions`, () =>
    HttpResponse.json({ items: [], total: 0 })
  ),

  // ---------------------------------------------------------------------------
  // Keys (client)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/keys`, () =>
    HttpResponse.json({
      items: [
        {
          id: "k1",
          name: "prod-key",
          key_prefix: "brg_abc",
          status: "active",
          created_at: "2024-01-01T00:00:00Z",
        },
      ],
      total: 1,
    })
  ),

  http.post(`${BASE}/keys`, () =>
    HttpResponse.json(
      {
        id: "k2",
        name: "new-key",
        key_prefix: "brg_xyz",
        secret: "brg_xyz_full-secret",
        status: "active",
        created_at: "2024-06-01T00:00:00Z",
      },
      { status: 201 }
    )
  ),

  http.patch(`${BASE}/keys/:id/revoke`, ({ params }) =>
    HttpResponse.json({ id: params.id, status: "revoked" })
  ),

  // ---------------------------------------------------------------------------
  // Client register / login
  // ---------------------------------------------------------------------------
  http.post(`${BASE}/clients/register`, () =>
    HttpResponse.json(
      { id: "c3", name: "New Corp", email: "new@corp.com", status: "pending" },
      { status: 201 }
    )
  ),

  http.post(`${BASE}/clients/login`, () =>
    HttpResponse.json({ access_token: "mock-client-token", token_type: "bearer" })
  ),

  // ---------------------------------------------------------------------------
  // Metrics dashboard (client)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/metrics/dashboard`, () =>
    HttpResponse.json({
      total_requests: 1250,
      error_rate: 2.5,
      avg_latency_ms: 87.3,
      total_cost: 12.5,
      billable_requests: 1100,
      non_billable_requests: 150,
    })
  ),

  // ---------------------------------------------------------------------------
  // Metrics (admin)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/metrics/admin`, () =>
    HttpResponse.json({
      total_requests: 8400,
      // error_rate é fração (0.012 = 1.2%) — AdminMetricsPage multiplica por 100
      error_rate: 0.012,
      avg_latency_ms: 64.0,
      total_cost: 87.5,
      billable_requests: 7800,
      non_billable_requests: 600,
    })
  ),

  // ---------------------------------------------------------------------------
  // Logs (client)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/logs`, () =>
    HttpResponse.json({
      items: [
        {
          correlation_id: "cid-1",
          path: "v1/charges",
          method: "POST",
          status_code: 200,
          latency_ms: 95.2,
        },
      ],
      total: 1,
    })
  ),
];
