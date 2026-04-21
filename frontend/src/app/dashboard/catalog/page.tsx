"use client";

import { useEffect, useState } from "react";
import { getCatalog } from "@/lib/api";
import Link from "next/link";

const BRIDGE_BASE =
  process.env.NEXT_PUBLIC_BRIDGE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

type ApiEntry = {
  id: string;
  name: string;
  slug?: string;
  base_url: string;
  url_template?: string;
  status: string;
};

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <button
      onClick={handleCopy}
      title="Copiar URL"
      className="ml-2 p-1 rounded hover:bg-surface-container-high transition-colors text-on-surface-variant hover:text-primary"
    >
      <span className="material-symbols-outlined text-[16px]">
        {copied ? "check" : "content_copy"}
      </span>
    </button>
  );
}

function ApiUrlBlock({ api }: { api: ApiEntry }) {
  if (api.slug) {
    const url = `${BRIDGE_BASE}/apis/${api.slug}/{query}/{seu-token}`;
    return (
      <div className="bg-surface-container-low rounded-lg p-4 mb-6 flex-1 space-y-3">
        <div className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
          Como usar
        </div>
        <div className="flex items-start gap-1">
          <code className="font-mono text-sm break-all leading-relaxed flex-1">
            <span className="text-on-surface-variant">{BRIDGE_BASE}/apis/</span>
            <span className="text-primary font-bold">{api.slug}</span>
            <span className="text-on-surface-variant">/</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-primary/10 text-primary text-xs font-bold">{"{query}"}</span>
            <span className="text-on-surface-variant">/</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-xs font-bold">{"{seu-token}"}</span>
          </code>
          <CopyButton value={url} />
        </div>
        <div className="flex gap-4 text-xs text-on-surface-variant">
          <span>
            <span className="inline-block w-2 h-2 rounded-sm bg-primary/20 mr-1" />
            <code className="font-mono">{"{query}"}</code> — o que você quer consultar
          </span>
          <span>
            <span className="inline-block w-2 h-2 rounded-sm bg-emerald-100 mr-1" />
            <code className="font-mono">{"{seu-token}"}</code> — sua chave Bridge{" "}
            <Link href="/dashboard/keys" className="text-primary hover:underline">
              ver chaves →
            </Link>
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-container-low rounded-lg p-4 mb-6 flex-1">
      <div className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-2">Base URL</div>
      <div className="flex items-center gap-1">
        <code className="font-mono text-sm text-tertiary flex-1 overflow-x-auto">{api.base_url}</code>
        <CopyButton value={api.base_url} />
      </div>
    </div>
  );
}

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
    <div className="max-w-6xl mx-auto">
      <div className="flex justify-between items-end mb-12">
        <div>
          <h1 className="text-4xl font-headline font-extrabold text-on-surface tracking-tight mb-2">API Catalog</h1>
          <p className="text-on-surface-variant text-lg max-w-2xl">
            Discover and integrate Bridge API services into your applications.
          </p>
        </div>
        <Link
          href="/dashboard/keys"
          className="primary-gradient text-white px-5 py-2.5 rounded-lg font-medium flex items-center gap-2 hover:opacity-90 transition-opacity shadow-[0_4px_14px_0_rgba(43,91,181,0.2)]"
        >
          <span className="material-symbols-outlined text-sm">vpn_key</span>
          Gerenciar Chaves
        </Link>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16 text-on-surface-variant gap-2">
          <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Carregando…
        </div>
      )}
      {error && <div role="alert" className="p-6 text-error bg-error-container rounded-xl">{error}</div>}

      {!loading && !error && (
        <>
          {catalog.length === 0 ? (
            <div className="text-center py-16 text-on-surface-variant">
              <span className="material-symbols-outlined text-5xl mb-4 block opacity-40">api</span>
              <p>Nenhuma API disponível para você ainda.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-16">
              {catalog.map((api, i) => (
                <div
                  key={api.id}
                  className="bg-surface-container-lowest rounded-xl p-8 border border-outline-variant/15 flex flex-col hover:shadow-[0_8px_30px_rgb(7,30,39,0.04)] transition-all"
                >
                  <div className="flex items-center gap-4 mb-4">
                    <div className="w-12 h-12 rounded-lg bg-surface-container-low flex items-center justify-center text-primary">
                      <span
                        className="material-symbols-outlined text-2xl"
                        style={{ fontVariationSettings: "'FILL' 1" }}
                      >
                        api
                      </span>
                    </div>
                    <div>
                      <h2 className="font-headline font-bold text-xl text-on-surface">{api.name}</h2>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`w-2 h-2 rounded-full ${api.status === "active" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]" : "bg-outline"}`} />
                        <span className="text-xs text-on-surface-variant uppercase tracking-wider font-semibold">
                          {api.status === "active" ? "Operational" : api.status}
                        </span>
                      </div>
                    </div>
                  </div>

                  <ApiUrlBlock api={api} />

                  <div className="flex items-center justify-between border-t border-outline-variant/10 pt-4">
                    <a href="#" className="text-primary text-sm font-medium hover:underline flex items-center gap-1">
                      View Documentation
                      <span className="material-symbols-outlined text-xs">arrow_forward</span>
                    </a>
                    <button className="bg-surface-container-high text-on-surface px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface-variant transition-colors">
                      Testar API
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
