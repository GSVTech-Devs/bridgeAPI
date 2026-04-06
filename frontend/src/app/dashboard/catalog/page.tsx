"use client";

import { useEffect, useState } from "react";
import { getCatalog } from "@/lib/api";

type ApiEntry = { id: string; name: string; base_url: string; status: string };

export default function CatalogPage() {
  const [catalog, setCatalog] = useState<ApiEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCatalog()
      .then((data) => setCatalog(data.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Catálogo de APIs</h1>
        <p className="text-gray-500 mt-1">APIs disponíveis para uso com suas chaves.</p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <svg className="animate-spin w-6 h-6 mr-2" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
          </svg>
          Carregando…
        </div>
      )}
      {error && <div role="alert" className="p-6 text-red-600 bg-red-50 rounded-xl">{error}</div>}

      {!loading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {catalog.length === 0 && (
            <p className="text-gray-400 col-span-3 py-10 text-center">Nenhuma API disponível para você ainda.</p>
          )}
          {catalog.map((api) => (
            <div key={api.id} className="card">
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <span className={api.status === "active" ? "badge-green" : "badge-gray"}>
                  {api.status === "active" ? "Ativa" : api.status}
                </span>
              </div>
              <h3 className="font-semibold text-gray-900 mt-3">{api.name}</h3>
              <p className="text-sm text-gray-500 font-mono mt-1 truncate">{api.base_url}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
