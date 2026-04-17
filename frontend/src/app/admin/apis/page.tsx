"use client";

import { useEffect, useRef, useState } from "react";
import { getApis, createApi, enableApi, disableApi } from "@/lib/api";

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
  auth_type: string;
};

const initialForm = {
  name: "",
  slug: "",
  base_url: "",
  url_template: "",
  auth_type: "api_key",
  master_key: "",
  description: "",
};

function Spinner() {
  return (
    <div className="flex items-center justify-center py-20 text-on-surface-variant gap-2">
      <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
      </svg>
      Carregando…
    </div>
  );
}

/** Renders a url_template with {query} and {token} as coloured badges. */
function TemplatePreview({ template }: { template: string }) {
  if (!template) return null;
  const parts = template.split(/(\{query\}|\{token\})/g);
  return (
    <span className="font-mono text-xs break-all">
      {parts.map((part, i) => {
        if (part === "{query}") return (
          <span key={i} className="inline-flex items-center px-1.5 py-0.5 rounded bg-primary/15 text-primary font-bold">QUERY</span>
        );
        if (part === "{token}") return (
          <span key={i} className="inline-flex items-center px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-bold">TOKEN</span>
        );
        return <span key={i} className="text-on-surface-variant">{part}</span>;
      })}
    </span>
  );
}

/** Shows the public Bridge URL the client will use. */
function BridgeUrlPreview({ slug }: { slug: string }) {
  if (!slug) return null;
  return (
    <div className="bg-surface-container-low rounded-xl px-4 py-3 flex items-start gap-2">
      <span className="material-symbols-outlined text-[16px] text-primary mt-0.5 shrink-0">link</span>
      <span className="font-mono text-xs break-all">
        <span className="text-on-surface-variant">{BRIDGE_BASE}/apis/</span>
        <span className="text-primary font-bold">{slug}</span>
        <span className="text-on-surface-variant">/</span>
        <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-primary/15 text-primary font-bold">QUERY</span>
        <span className="text-on-surface-variant">/</span>
        <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-bold">TOKEN</span>
      </span>
    </div>
  );
}

function UrlTemplateBuilder({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  function insertPlaceholder(placeholder: string) {
    const el = inputRef.current;
    if (!el) return;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const next = value.slice(0, start) + placeholder + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + placeholder.length, start + placeholder.length);
    });
  }

  const hasQuery = value.includes("{query}");
  const hasToken = value.includes("{token}");

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          className="flex-1 bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none font-mono text-sm"
          placeholder="https://api.example.com/v1/{query}/{token}"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-on-surface-variant font-medium">Inserir:</span>
        <button type="button" onClick={() => insertPlaceholder("{query}")}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-primary/10 text-primary hover:bg-primary/20 transition-colors">
          <span className="material-symbols-outlined text-[14px]">search</span>
          {"{query}"}{hasQuery && <span className="material-symbols-outlined text-[14px]">check</span>}
        </button>
        <button type="button" onClick={() => insertPlaceholder("{token}")}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors">
          <span className="material-symbols-outlined text-[14px]">vpn_key</span>
          {"{token}"}{hasToken && <span className="material-symbols-outlined text-[14px]">check</span>}
        </button>
        {value && (
          <button type="button" onClick={() => onChange("")}
            className="ml-auto text-xs text-on-surface-variant hover:text-error transition-colors">
            Limpar
          </button>
        )}
      </div>
      {value && <div className="bg-surface-container-low rounded-xl px-4 py-3 flex items-start gap-2">
        <span className="material-symbols-outlined text-[16px] text-on-surface-variant mt-0.5 shrink-0">link</span>
        <TemplatePreview template={value} />
      </div>}
      {value && !hasQuery && (
        <p className="text-xs text-error">O template deve conter <code className="font-bold">{"{query}"}</code>.</p>
      )}
      {hasToken && (
        <p className="text-xs text-on-surface-variant">O token será inserido na URL — não será enviado como header.</p>
      )}
    </div>
  );
}

export default function ApisPage() {
  const [apis, setApis] = useState<Api[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState(false);

  async function load() {
    try {
      const data = await getApis();
      setApis(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleToggle(api: Api) {
    setActionLoading(api.id);
    try {
      if (api.status === "active") {
        await disableApi(api.id);
        setApis((prev) => prev.map((a) => a.id === api.id ? { ...a, status: "inactive" } : a));
      } else {
        await enableApi(api.id);
        setApis((prev) => prev.map((a) => a.id === api.id ? { ...a, status: "active" } : a));
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro na operação");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError(null);
    try {
      const payload = {
        ...form,
        slug: form.slug || undefined,
        url_template: form.url_template || undefined,
      };
      const api = await createApi(payload);
      setApis((prev) => [...prev, api]);
      setForm(initialForm);
      setShowForm(false);
      setFormSuccess(true);
      setTimeout(() => setFormSuccess(false), 3000);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Erro ao cadastrar");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-extrabold font-headline tracking-tighter text-on-surface">API Catalog</h2>
          <p className="text-on-surface-variant mt-2 text-lg">Manage, monitor and connect your technical assets through Bridge.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="primary-gradient text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 hover:scale-[1.02] transition-transform shadow-lg shadow-primary/20"
        >
          <span className="material-symbols-outlined">add_circle</span>
          {showForm ? "Cancelar" : "Register New API"}
        </button>
      </div>

      {formSuccess && (
        <div className="p-4 bg-green-100 text-green-800 rounded-xl text-sm font-medium">
          API cadastrada com sucesso!
        </div>
      )}

      {/* Registration form */}
      {showForm && (
        <section className="bg-surface-container-lowest rounded-xl p-10 border border-outline-variant/15 relative overflow-hidden">
          <div className="max-w-4xl mx-auto">
            <div className="mb-8 flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl primary-gradient flex items-center justify-center text-white shadow-lg">
                <span className="material-symbols-outlined text-2xl">add_link</span>
              </div>
              <div>
                <h3 className="text-2xl font-extrabold font-headline text-on-surface">Register New API</h3>
                <p className="text-on-surface-variant">Configure your endpoint transformation and pricing structure.</p>
              </div>
            </div>

            {formError && (
              <div role="alert" className="mb-6 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreate} className="space-y-6">
              {/* Row 1: name + slug */}
              <div className="grid grid-cols-2 gap-x-10">
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-on-surface-variant">API Name</label>
                  <input
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                    placeholder="e.g. Real-Time Finance Connector"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <label className="block text-sm font-bold text-on-surface-variant">Slug público</label>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">opcional</span>
                  </div>
                  <input
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none font-mono text-sm"
                    placeholder="consulta"
                    value={form.slug}
                    onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") }))}
                  />
                  <p className="text-xs text-on-surface-variant">Letras, números, hífens e underscores.</p>
                </div>
              </div>

              {/* Bridge URL preview */}
              {form.slug && (
                <div className="space-y-1">
                  <p className="text-xs font-bold text-on-surface-variant">URL pública no Bridge</p>
                  <BridgeUrlPreview slug={form.slug} />
                </div>
              )}

              {/* Row 2: base_url + auth type */}
              <div className="grid grid-cols-2 gap-x-10">
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-on-surface-variant">Base URL da API original</label>
                  <input
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                    placeholder="https://api.provider.com/v1"
                    value={form.base_url}
                    onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-on-surface-variant">Auth Type</label>
                  <select
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                    value={form.auth_type}
                    onChange={(e) => setForm((f) => ({ ...f, auth_type: e.target.value }))}
                  >
                    <option value="api_key">API Key</option>
                    <option value="bearer">Bearer Token</option>
                    <option value="basic">Basic Auth</option>
                    <option value="none">Sem autenticação</option>
                  </select>
                </div>
              </div>

              {/* Master key */}
              <div className="space-y-2">
                <label className="block text-sm font-bold text-on-surface-variant">Master Key / Token da API original</label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]">vpn_key</span>
                  <input
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 pl-12 pr-5 text-on-surface focus:ring-2 focus:ring-primary-container transition-all outline-none font-mono text-sm"
                    type="password"
                    placeholder="••••••••••••••••"
                    value={form.master_key}
                    onChange={(e) => setForm((f) => ({ ...f, master_key: e.target.value }))}
                    required
                  />
                </div>
              </div>

              {/* URL Template builder */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <label className="block text-sm font-bold text-on-surface-variant">URL Template da API original</label>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">opcional</span>
                </div>
                <p className="text-xs text-on-surface-variant">
                  Se a API original exige o token ou a query em posições específicas na URL. Deixe vazio para usar{" "}
                  <code className="font-mono">Base URL + query</code> com auth no header.
                </p>
                <UrlTemplateBuilder
                  value={form.url_template}
                  onChange={(v) => setForm((f) => ({ ...f, url_template: v }))}
                />
              </div>

              {/* Description */}
              <div className="space-y-2">
                <label className="block text-sm font-bold text-on-surface-variant">Description (optional)</label>
                <input
                  className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                  placeholder="Breve descrição da API"
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>

              <div className="flex justify-end gap-4 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-8 py-4 rounded-xl font-bold text-on-surface-variant hover:bg-surface-container-high transition-colors">
                  Discard
                </button>
                <button type="submit" disabled={formLoading}
                  className="primary-gradient text-white px-12 py-4 rounded-xl font-extrabold shadow-xl shadow-primary/30 hover:scale-[1.03] transition-transform disabled:opacity-70">
                  {formLoading ? "Cadastrando…" : "Deploy API Bridge"}
                </button>
              </div>
            </form>
          </div>
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/5 rounded-full blur-3xl" />
        </section>
      )}

      {/* APIs table */}
      <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
        <div className="px-6 py-5 flex items-center justify-between">
          <h3 className="font-bold text-xl font-headline">Connected Endpoints</h3>
          <span className="text-sm text-primary font-bold">Live Status</span>
        </div>

        {loading && <Spinner />}
        {error && <div role="alert" className="p-6 text-error bg-error-container/20">{error}</div>}

        {!loading && !error && (
          <div className="space-y-2 px-4 pb-4">
            <div className="grid grid-cols-4 px-4 py-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant/60">
              <div>API Service</div>
              <div>Bridge URL / Upstream</div>
              <div>Status</div>
              <div className="text-right">Actions</div>
            </div>

            {apis.length === 0 && (
              <div className="text-center py-10 text-on-surface-variant">Nenhuma API cadastrada</div>
            )}

            {apis.map((api) => (
              <div key={api.id}
                className="grid grid-cols-4 items-center px-4 py-5 bg-surface-container-low rounded-xl hover:bg-surface-container-high transition-colors group">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-[20px]">dataset</span>
                  </div>
                  <div>
                    <p className="font-bold text-sm">{api.name}</p>
                    <p className="text-xs text-on-surface-variant">{api.auth_type}</p>
                  </div>
                </div>
                <div className="pr-4 overflow-hidden space-y-1">
                  {api.slug ? (
                    <div className="font-mono text-xs flex items-center gap-1 flex-wrap">
                      <span className="text-on-surface-variant/60 text-[10px]">bridge:</span>
                      <span className="text-on-surface-variant">/apis/</span>
                      <span className="text-primary font-bold">{api.slug}</span>
                      <span className="text-on-surface-variant">/</span>
                      <span className="px-1 rounded bg-primary/10 text-primary text-[10px] font-bold">QUERY</span>
                      <span className="text-on-surface-variant">/</span>
                      <span className="px-1 rounded bg-green-100 text-green-700 text-[10px] font-bold">TOKEN</span>
                    </div>
                  ) : api.url_template ? (
                    <TemplatePreview template={api.url_template} />
                  ) : (
                    <span className="font-mono text-xs text-on-surface-variant truncate block">{api.base_url}</span>
                  )}
                </div>
                <div>
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${
                    api.status === "active" ? "bg-green-100 text-green-700" : "bg-surface-variant text-on-surface-variant"
                  }`}>
                    {api.status === "active" ? "Active" : "Inactive"}
                  </span>
                </div>
                <div className="text-right opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => handleToggle(api)} disabled={actionLoading === api.id}
                    className={`p-2 rounded-lg text-sm font-bold transition-colors ${
                      api.status === "active" ? "hover:bg-error-container text-error" : "hover:bg-green-100 text-green-700"
                    }`}>
                    <span className="material-symbols-outlined text-sm">
                      {actionLoading === api.id ? "hourglass_empty" : api.status === "active" ? "toggle_off" : "toggle_on"}
                    </span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
