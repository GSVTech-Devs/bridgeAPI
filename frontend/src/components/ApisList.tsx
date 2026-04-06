"use client";

import { useEffect, useState } from "react";
import { getApis, disableApi } from "@/lib/api";

type Api = {
  id: string;
  name: string;
  base_url: string;
  status: string;
  auth_type: string;
};

export default function ApisList() {
  const [apis, setApis] = useState<Api[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await getApis();
      setApis(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar APIs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <p>Carregando…</p>;
  if (error) return <div role="alert">{error}</div>;

  return (
    <ul>
      {apis.map((a) => (
        <li key={a.id}>
          <span>{a.name}</span>
          <span> — </span>
          <span>{a.base_url}</span>
          <span> — </span>
          <span>{a.status}</span>
          {a.status === "active" && (
            <button onClick={() => disableApi(a.id)}>Desabilitar</button>
          )}
        </li>
      ))}
    </ul>
  );
}
