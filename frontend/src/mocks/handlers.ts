import { http, HttpResponse } from "msw";

const BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export const handlers = [
  http.post(`${BASE}/auth/login`, () =>
    HttpResponse.json({ access_token: "mock-token", token_type: "bearer" })
  ),

  http.get(`${BASE}/auth/me`, () =>
    HttpResponse.json({ email: "admin@bridge.dev", role: "admin", account_id: null })
  ),

  http.patch(`${BASE}/auth/portal/password`, () => new HttpResponse(null, { status: 204 })),

  // ---------------------------------------------------------------------------
  // Accounts (admin)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/admin/accounts`, () =>
    HttpResponse.json({
      items: [
        {
          id: "c1",
          name: "Acme Corp",
          type: "company",
          status: "active",
          created_at: "2024-01-01T00:00:00Z",
          owner_email: "owner@acme.com",
          owner_id: "u1",
        },
        {
          id: "c2",
          name: "Beta",
          type: "individual",
          status: "blocked",
          created_at: "2024-02-01T00:00:00Z",
          owner_email: "beta@user.com",
          owner_id: "u2",
        },
      ],
      total: 2,
    })
  ),

  http.post(`${BASE}/admin/users`, () =>
    HttpResponse.json(
      {
        account: { id: "c3", name: "New User", type: "individual", status: "active" },
        owner_email: "new@user.com",
        owner_id: "u3",
      },
      { status: 201 }
    )
  ),

  http.post(`${BASE}/admin/companies`, () =>
    HttpResponse.json(
      {
        account: { id: "c4", name: "New Co", type: "company", status: "active" },
        owner_email: "boss@newco.com",
        owner_id: "u4",
      },
      { status: 201 }
    )
  ),

  http.patch(`${BASE}/admin/accounts/:id/credentials`, async ({ params, request }) => {
    const body = (await request.json()) as { email?: string; password?: string };
    return HttpResponse.json({
      account_id: params.id,
      owner_id: "u1",
      owner_email: body.email ?? "owner@acme.com",
    });
  }),

  http.patch(`${BASE}/admin/accounts/:id/block`, ({ params }) =>
    HttpResponse.json({ id: params.id, status: "blocked" })
  ),

  http.patch(`${BASE}/admin/accounts/:id/unblock`, ({ params }) =>
    HttpResponse.json({ id: params.id, status: "active" })
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
    HttpResponse.json({ account_id: "c1", api_id: "a1" }, { status: 201 })
  ),

  http.patch(`${BASE}/permissions/:accountId/:apiId/revoke`, ({ params }) =>
    HttpResponse.json({ account_id: params.accountId, api_id: params.apiId })
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
          slug: "stripe",
          base_url: "https://api.stripe.com",
          url_template: "https://api.stripe.com/v1/{query}",
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
          api_id: "a1",
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
        api_id: "a1",
        name: "new-key",
        key_prefix: "brg_xyz",
        api_key: "brg_xyz_full-secret",
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
  // Portal login (account users)
  // ---------------------------------------------------------------------------
  http.post(`${BASE}/auth/portal/login`, () =>
    HttpResponse.json({ access_token: "mock-portal-token", token_type: "bearer" })
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

  http.get(`${BASE}/metrics/admin/breakdown`, () =>
    HttpResponse.json({
      items: [
        { api_id: "a1", api_name: "Stripe", total_requests: 5000, error_rate: 1.2 },
      ],
    })
  ),

  http.get(`${BASE}/metrics/admin/usage`, () =>
    HttpResponse.json({
      items: [
        {
          client_id: "c1",
          client_name: "Acme Corp",
          client_email: "owner@acme.com",
          api_id: "a1",
          api_name: "Stripe",
          total_requests: 5000,
          total_cost: 50.0,
        },
      ],
    })
  ),

  http.get(`${BASE}/logs/admin`, () =>
    HttpResponse.json({
      items: [
        {
          correlation_id: "cid-a",
          client_id: "c1",
          api_id: "a1",
          path: "v1/charges",
          method: "POST",
          status_code: 200,
          latency_ms: 80.0,
          created_at: "2024-06-01T00:00:00Z",
        },
      ],
      total: 1,
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
