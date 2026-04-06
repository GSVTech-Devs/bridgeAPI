"use client";

import { useEffect, useState } from "react";
import { getClientDashboard } from "@/lib/api";

type Metrics = {
  total_requests: number;
  error_rate: number;
  avg_latency_ms: number;
  total_cost: number;
  billable_requests: number;
  non_billable_requests: number;
};

export default function MetricsDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClientDashboard()
      .then(setMetrics)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erro ao carregar métricas")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Carregando…</p>;
  if (error) return <div role="alert">{error}</div>;
  if (!metrics) return null;

  return (
    <div>
      <section>
        <h2>Total de Requisições</h2>
        <p>{metrics.total_requests}</p>
      </section>
      <section>
        <h2>Taxa de Erro (%)</h2>
        <p data-testid="error-rate">{metrics.error_rate}</p>
      </section>
      <section>
        <h2>Latência Média (ms)</h2>
        <p data-testid="avg-latency">{metrics.avg_latency_ms}</p>
      </section>
      <section>
        <h2>Custo Total</h2>
        <p data-testid="total-cost">{metrics.total_cost}</p>
      </section>
      <section>
        <h2>Billable</h2>
        <p>{metrics.billable_requests}</p>
      </section>
      <section>
        <h2>Non-Billable</h2>
        <p>{metrics.non_billable_requests}</p>
      </section>
    </div>
  );
}
