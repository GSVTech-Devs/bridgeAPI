"use client";

import { useEffect, useState } from "react";
import { getCatalog } from "@/lib/api";

type Api = { id: string; name: string; base_url: string; status: string };

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
          <span> — {a.base_url}</span>
          <span> — {a.status}</span>
        </li>
      ))}
    </ul>
  );
}
