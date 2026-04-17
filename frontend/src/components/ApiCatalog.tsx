"use client";

import { useEffect, useState } from "react";
import { getCatalog } from "@/lib/api";

const BRIDGE_BASE =
  process.env.NEXT_PUBLIC_BRIDGE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

type Api = {
  id: string;
  name: string;
  slug?: string;
  base_url: string;
  url_template?: string;
  status: string;
};

function BridgeUrl({ slug }: { slug: string }) {
  return (
    <span data-testid="bridge-url" className="font-mono text-sm break-all">
      {BRIDGE_BASE}/apis/{slug}/
      <span className="text-primary font-bold">{"{query}"}</span>/
      <span className="text-emerald-600 font-bold">{"{seu-token}"}</span>
    </span>
  );
}

export default function ApiCatalog() {
  const [apis, setApis] = useState<Api[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCatalog()
      .then((data) => setApis(data.items))
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erro ao carregar catálogo")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Carregando…</p>;
  if (error) return <div role="alert">{error}</div>;
  if (apis.length === 0) return <p>Nenhuma API autorizada</p>;

  return (
    <ul>
      {apis.map((a) => (
        <li key={a.id}>
          <strong>{a.name}</strong>
          {a.slug ? (
            <> — <BridgeUrl slug={a.slug} /></>
          ) : (
            <span> — {a.base_url}</span>
          )}
          <span> — {a.status}</span>
        </li>
      ))}
    </ul>
  );
}
