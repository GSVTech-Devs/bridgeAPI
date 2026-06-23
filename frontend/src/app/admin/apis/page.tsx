"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getApis, createApi, updateApi, enableApi, disableApi, deleteApi,
  getApiProxies, createApiProxy, updateApiProxy, deleteApiProxy,
  getApiCaptchas, createApiCaptcha, updateApiCaptcha, deleteApiCaptcha,
  importOpenApi,
  type Proxy, type ProxyInput, type Captcha, type CaptchaInput, type ImportedOperation,
} from "@/lib/api";

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
  request_method?: string | null;
  request_body_template?: string | null;
  status: string;
  auth_type: string;
  cost_per_query?: number;
  uses_proxy?: boolean;
  uses_captcha?: boolean;
};

const initialForm = {
  name: "",
  slug: "",
  base_url: "",
  url_template: "",
  auth_type: "api_key",
  master_key: "",
  cost_per_query: "",
  request_method: "",
  request_body_template: "",
  uses_proxy: false,
  uses_captcha: false,
  description: "",
};

type FormErrors = Partial<Record<keyof typeof initialForm, string>>;

function validateForm(form: typeof initialForm): FormErrors {
  const errors: FormErrors = {};

  if (!form.name.trim()) {
    errors.name = "API Name is required.";
  }

  if (!form.base_url.trim()) {
    errors.base_url = "Base URL is required.";
  } else if (!/^https?:\/\/.+/.test(form.base_url.trim())) {
    errors.base_url = "Must be a valid URL starting with http:// or https://.";
  }

  if (form.auth_type !== "none" && !form.master_key.trim()) {
    errors.master_key = "Master key is required for this auth type.";
  }

  if (form.url_template.trim()) {
    if (!/^https?:\/\//.test(form.url_template.trim())) {
      errors.url_template = "URL Template must start with http:// or https://.";
    } else if (!form.url_template.includes("{query}")) {
      errors.url_template = "URL Template must contain the {query} placeholder.";
    }
  }

  if (form.cost_per_query.trim()) {
    const v = parseFloat(form.cost_per_query);
    if (isNaN(v) || v < 0) {
      errors.cost_per_query = "Cost must be a positive number.";
    }
  }

  return errors;
}

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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(initialForm);
  const [fieldErrors, setFieldErrors] = useState<FormErrors>({});
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Import de OpenAPI/Swagger
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importLoading, setImportLoading] = useState(false);
  const [importErr, setImportErr] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{
    title?: string | null; base_url?: string | null; operations: ImportedOperation[];
  } | null>(null);

  async function parseImport() {
    setImportLoading(true); setImportErr(null); setImportResult(null);
    try {
      setImportResult(await importOpenApi(importText));
    } catch (e) {
      setImportErr(e instanceof Error ? e.message : "Falha ao parsear o spec");
    } finally {
      setImportLoading(false);
    }
  }

  function applyOperation(op: ImportedOperation) {
    const server = (importResult?.base_url ?? "").replace(/\/$/, "");
    const path = op.path.startsWith("/") ? op.path : `/${op.path}`;
    const name = importResult?.title
      ? `${importResult.title}${op.summary ? ` — ${op.summary}` : ""}`
      : op.summary || op.path;
    setEditingId(null);
    setForm({
      ...initialForm,
      name: name.slice(0, 120),
      base_url: server ? `${server}${path}` : "",
      request_method: op.method,
      request_body_template: op.request_body_template ?? "",
    });
    setFieldErrors({});
    setFormError(null);
    setShowImport(false);
    setShowForm(true);
  }

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

  async function handleDelete(id: string) {
    setActionLoading(id);
    try {
      await deleteApi(id);
      setApis((prev) => prev.filter((a) => a.id !== id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
    } finally {
      setActionLoading(null);
      setDeleteConfirm(null);
    }
  }

  function openEdit(api: Api) {
    setEditingId(api.id);
    setForm({
      name: api.name,
      slug: api.slug ?? "",
      base_url: api.base_url,
      url_template: api.url_template ?? "",
      auth_type: api.auth_type,
      master_key: "",
      cost_per_query: api.cost_per_query != null ? String(api.cost_per_query) : "",
      request_method: api.request_method ?? "",
      request_body_template: api.request_body_template ?? "",
      uses_proxy: api.uses_proxy ?? false,
      uses_captcha: api.uses_captcha ?? false,
      description: "",
    });
    setFieldErrors({});
    setFormError(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingId(null);
    setForm(initialForm);
    setFieldErrors({});
    setFormError(null);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (editingId) { await handleUpdate(e); return; }
    const errors = validateForm(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    setFormLoading(true);
    setFormError(null);
    try {
      const costValue = form.cost_per_query ? parseFloat(form.cost_per_query) : undefined;
      const payload = {
        ...form,
        slug: form.slug || undefined,
        url_template: form.url_template || undefined,
        cost_per_query: costValue && !isNaN(costValue) ? costValue : undefined,
      };
      const api = await createApi(payload);
      setApis((prev) => [...prev, api]);
      setForm(initialForm);
      setFieldErrors({});
      setShowForm(false);
      setFormSuccess(true);
      setTimeout(() => setFormSuccess(false), 3000);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Erro ao cadastrar");
    } finally {
      setFormLoading(false);
    }
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId) return;
    const errors = validateForm({ ...form, master_key: form.master_key || "placeholder" });
    delete errors.master_key;
    if (Object.keys(errors).length > 0) { setFieldErrors(errors); return; }
    setFieldErrors({});
    setFormLoading(true);
    setFormError(null);
    try {
      const costValue = form.cost_per_query ? parseFloat(form.cost_per_query) : undefined;
      const payload: Parameters<typeof updateApi>[1] = {
        name: form.name || undefined,
        slug: form.slug || undefined,
        base_url: form.base_url || undefined,
        url_template: form.url_template || undefined,
        auth_type: form.auth_type || undefined,
        cost_per_query: costValue && !isNaN(costValue) ? costValue : undefined,
        request_method: form.request_method,
        request_body_template: form.request_body_template,
        uses_proxy: form.uses_proxy,
        uses_captcha: form.uses_captcha,
      };
      if (form.master_key) payload.master_key = form.master_key;
      const updated = await updateApi(editingId, payload);
      setApis((prev) => prev.map((a) => a.id === editingId ? { ...a, ...updated } : a));
      closeForm();
      setFormSuccess(true);
      setTimeout(() => setFormSuccess(false), 3000);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Erro ao atualizar");
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
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setImportErr(null); setImportResult(null); setShowImport(true); }}
            className="px-5 py-3 rounded-xl font-bold flex items-center gap-2 bg-surface-container-high text-on-surface hover:brightness-95 transition-all"
          >
            <span className="material-symbols-outlined">upload_file</span>
            Importar OpenAPI
          </button>
          <button
            onClick={() => { if (showForm) { closeForm(); } else { setShowForm(true); } }}
            className="primary-gradient text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 hover:scale-[1.02] transition-transform shadow-lg shadow-primary/20"
          >
            <span className="material-symbols-outlined">add_circle</span>
            {showForm ? "Cancelar" : "Register New API"}
          </button>
        </div>
      </div>

      {/* Modal de import de OpenAPI/Swagger */}
      {showImport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowImport(false)}>
          <div onClick={(e) => e.stopPropagation()}
            className="bg-surface-container-lowest rounded-2xl p-6 w-full max-w-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-bold text-on-surface">Importar OpenAPI / Swagger</h3>
              <button onClick={() => setShowImport(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <p className="text-sm text-on-surface-variant">
              Cole o JSON ou YAML da doc da API. Escolha uma operação para pré-preencher o cadastro
              (base URL, método e body template).
            </p>
            <textarea
              rows={8}
              className="w-full bg-surface-container-low border-none rounded-xl py-3 px-4 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container outline-none font-mono text-xs"
              placeholder='{"openapi":"3.0.0", ...}  ou  openapi: 3.0.0 ...'
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
            />
            {importErr && <div className="bg-error-container/30 text-error rounded-lg px-4 py-2 text-sm">{importErr}</div>}
            <div className="flex justify-end">
              <button onClick={parseImport} disabled={importLoading || !importText.trim()}
                className="px-5 py-2 rounded-lg bg-primary text-white font-bold text-sm hover:opacity-90 disabled:opacity-50">
                {importLoading ? "Lendo…" : "Ler spec"}
              </button>
            </div>

            {importResult && (
              <div className="space-y-2">
                <p className="text-xs text-on-surface-variant">
                  {importResult.title ?? "API"} · {importResult.base_url ?? "sem servidor"} ·{" "}
                  {importResult.operations.length} operação(ões)
                </p>
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 divide-y divide-outline-variant/10 max-h-72 overflow-y-auto">
                  {importResult.operations.length === 0 && (
                    <p className="py-6 text-center text-on-surface-variant text-sm">Nenhuma operação encontrada.</p>
                  )}
                  {importResult.operations.map((op, i) => (
                    <button key={i} onClick={() => applyOperation(op)}
                      className="w-full text-left px-4 py-3 hover:bg-surface-container-high transition-colors flex items-center gap-3">
                      <span className={`text-[10px] font-black uppercase rounded-md px-2 py-1 ${
                        op.request_body_template ? "bg-primary/15 text-primary" : "bg-surface-container-high text-on-surface-variant"
                      }`}>{op.method}</span>
                      <span className="min-w-0 flex-1">
                        <span className="font-mono text-xs text-on-surface truncate block">{op.path}</span>
                        {op.summary && <span className="text-xs text-on-surface-variant truncate block">{op.summary}</span>}
                      </span>
                      <span className="material-symbols-outlined text-on-surface-variant text-[18px]">arrow_forward</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

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
                <h3 className="text-2xl font-extrabold font-headline text-on-surface">
                  {editingId ? "Edit API" : "Register New API"}
                </h3>
                <p className="text-on-surface-variant">
                  {editingId ? "Update the API configuration below." : "Configure your endpoint transformation and pricing structure."}
                </p>
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
                    className={`w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 transition-all outline-none text-sm ${fieldErrors.name ? "ring-2 ring-error" : "focus:ring-primary-container"}`}
                    placeholder="e.g. Real-Time Finance Connector"
                    value={form.name}
                    onChange={(e) => { setForm((f) => ({ ...f, name: e.target.value })); setFieldErrors((fe) => ({ ...fe, name: undefined })); }}
                  />
                  {fieldErrors.name && <p className="text-xs text-error">{fieldErrors.name}</p>}
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
                    className={`w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 transition-all outline-none text-sm ${fieldErrors.base_url ? "ring-2 ring-error" : "focus:ring-primary-container"}`}
                    placeholder="https://api.provider.com/v1"
                    value={form.base_url}
                    onChange={(e) => { setForm((f) => ({ ...f, base_url: e.target.value })); setFieldErrors((fe) => ({ ...fe, base_url: undefined })); }}
                  />
                  {fieldErrors.base_url && <p className="text-xs text-error">{fieldErrors.base_url}</p>}
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
                <div className="flex items-center gap-2">
                  <label className="block text-sm font-bold text-on-surface-variant">Master Key / Token da API original</label>
                  {(form.auth_type === "none" || editingId) && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">
                      {editingId ? "deixe vazio para manter" : "opcional"}
                    </span>
                  )}
                </div>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]">vpn_key</span>
                  <input
                    className={`w-full bg-surface-container-low border-none rounded-xl py-4 pl-12 pr-5 text-on-surface focus:ring-2 transition-all outline-none font-mono text-sm ${fieldErrors.master_key ? "ring-2 ring-error" : "focus:ring-primary-container"}`}
                    type="password"
                    placeholder="••••••••••••••••"
                    value={form.master_key}
                    onChange={(e) => { setForm((f) => ({ ...f, master_key: e.target.value })); setFieldErrors((fe) => ({ ...fe, master_key: undefined })); }}
                  />
                </div>
                {fieldErrors.master_key && <p className="text-xs text-error">{fieldErrors.master_key}</p>}
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
                  onChange={(v) => { setForm((f) => ({ ...f, url_template: v })); setFieldErrors((fe) => ({ ...fe, url_template: undefined })); }}
                />
                {fieldErrors.url_template && <p className="text-xs text-error">{fieldErrors.url_template}</p>}
              </div>

              {/* Método na API original + body template (API POST) */}
              <div className="grid grid-cols-2 gap-x-10">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <label className="block text-sm font-bold text-on-surface-variant">Método na API original</label>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">opcional</span>
                  </div>
                  <select
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                    value={form.request_method}
                    onChange={(e) => setForm((f) => ({ ...f, request_method: e.target.value }))}
                  >
                    <option value="">Repassar o método do cliente</option>
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                  <p className="text-xs text-on-surface-variant">
                    Vazio = a Bridge chama a API original com o mesmo método do cliente.
                  </p>
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-on-surface-variant">Body template (API POST)</label>
                  <textarea
                    rows={3}
                    className="w-full bg-surface-container-low border-none rounded-xl py-3 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none font-mono text-xs"
                    placeholder={'{"q": "{query}", "key": "{token}"}'}
                    value={form.request_body_template}
                    onChange={(e) => setForm((f) => ({ ...f, request_body_template: e.target.value }))}
                  />
                  <p className="text-xs text-on-surface-variant">
                    Renderiza <code className="font-mono">{"{query}"}</code> e <code className="font-mono">{"{token}"}</code>.
                    Vazio = repassa o body do cliente.
                  </p>
                </div>
              </div>

              {/* Row: cost_per_query + description */}
              <div className="grid grid-cols-2 gap-x-10">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <label className="block text-sm font-bold text-on-surface-variant">Valor por consulta (R$)</label>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">opcional</span>
                  </div>
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]">payments</span>
                    <input
                      className={`w-full bg-surface-container-low border-none rounded-xl py-4 pl-12 pr-5 text-on-surface placeholder:text-outline-variant focus:ring-2 transition-all outline-none text-sm ${fieldErrors.cost_per_query ? "ring-2 ring-error" : "focus:ring-primary-container"}`}
                      type="number"
                      min="0"
                      step="0.001"
                      placeholder="0.050"
                      value={form.cost_per_query}
                      onChange={(e) => { setForm((f) => ({ ...f, cost_per_query: e.target.value })); setFieldErrors((fe) => ({ ...fe, cost_per_query: undefined })); }}
                    />
                  </div>
                  {fieldErrors.cost_per_query
                    ? <p className="text-xs text-error">{fieldErrors.cost_per_query}</p>
                    : <p className="text-xs text-on-surface-variant">Cobrado por requisição bem-sucedida.</p>
                  }
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-on-surface-variant">Description (optional)</label>
                  <input
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                    placeholder="Breve descrição da API"
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  />
                </div>
              </div>

              {/* Usa proxy? */}
              <label className="flex items-center gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.uses_proxy}
                  onChange={(e) => setForm((f) => ({ ...f, uses_proxy: e.target.checked }))}
                  className="h-5 w-5 rounded accent-primary"
                />
                <span className="text-sm text-on-surface">
                  Esta API usa proxy
                  <span className="block text-xs text-on-surface-variant">
                    Os proxies são configurados em “Proxies”, por API.
                  </span>
                </span>
              </label>

              {/* Usa captcha? */}
              <label className="flex items-center gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.uses_captcha}
                  onChange={(e) => setForm((f) => ({ ...f, uses_captcha: e.target.checked }))}
                  className="h-5 w-5 rounded accent-primary"
                />
                <span className="text-sm text-on-surface">
                  Esta API usa captcha
                  <span className="block text-xs text-on-surface-variant">
                    Os provedores são configurados em “Captcha”, por API.
                  </span>
                </span>
              </label>

              <div className="flex justify-end gap-4 pt-2">
                <button type="button" onClick={closeForm}
                  className="px-8 py-4 rounded-xl font-bold text-on-surface-variant hover:bg-surface-container-high transition-colors">
                  Cancelar
                </button>
                <button type="submit" disabled={formLoading}
                  className="primary-gradient text-white px-12 py-4 rounded-xl font-extrabold shadow-xl shadow-primary/30 hover:scale-[1.03] transition-transform disabled:opacity-70">
                  {formLoading
                    ? (editingId ? "Salvando…" : "Cadastrando…")
                    : (editingId ? "Salvar Alterações" : "Deploy API Bridge")}
                </button>
              </div>
            </form>

            {/* Proxy/captcha da API — só em edição (precisa do api_id salvo) */}
            {editingId && (form.uses_proxy || form.uses_captcha) && (
              <div className="mt-10 space-y-8 border-t border-outline-variant/15 pt-8">
                {form.uses_proxy && <ApiProxyPanel apiId={editingId} />}
                {form.uses_captcha && <ApiCaptchaPanel apiId={editingId} />}
              </div>
            )}
            {!editingId && (form.uses_proxy || form.uses_captcha) && (
              <p className="mt-6 text-xs text-on-surface-variant max-w-4xl mx-auto">
                Salve a API para configurar {form.uses_proxy ? "proxies" : ""}
                {form.uses_proxy && form.uses_captcha ? " e " : ""}
                {form.uses_captcha ? "captcha" : ""} aqui.
              </p>
            )}
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
                <div className="text-right flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {deleteConfirm === api.id ? (
                    <>
                      <span className="text-xs text-on-surface-variant mr-1">Confirmar exclusão?</span>
                      <button
                        onClick={() => handleDelete(api.id)}
                        disabled={actionLoading === api.id}
                        aria-label="Confirmar exclusão"
                        className="px-3 py-1.5 rounded-lg text-xs font-bold bg-error text-on-error hover:opacity-90 transition-opacity disabled:opacity-50"
                      >
                        {actionLoading === api.id ? "…" : "Excluir"}
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold text-on-surface-variant hover:bg-surface-container-high transition-colors"
                      >
                        Cancelar
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => openEdit(api)}
                        aria-label="Editar API"
                        className="p-2 rounded-lg text-sm font-bold text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors"
                      >
                        <span className="material-symbols-outlined text-sm">edit</span>
                      </button>
                      <button onClick={() => handleToggle(api)} disabled={actionLoading === api.id}
                        className={`p-2 rounded-lg text-sm font-bold transition-colors ${
                          api.status === "active" ? "hover:bg-error-container text-error" : "hover:bg-green-100 text-green-700"
                        }`}>
                        <span className="material-symbols-outlined text-sm">
                          {actionLoading === api.id ? "hourglass_empty" : api.status === "active" ? "toggle_off" : "toggle_on"}
                        </span>
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(api.id)}
                        aria-label="Excluir API"
                        className="p-2 rounded-lg text-sm font-bold text-on-surface-variant hover:bg-error-container hover:text-error transition-colors"
                      >
                        <span className="material-symbols-outlined text-sm">delete</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Painéis embutidos no cadastro da API: proxies e captchas desta API (admin).
// ---------------------------------------------------------------------------
function statusPill(s: string): string {
  switch (s) {
    case "active": return "bg-green-600 text-white";
    case "failing": return "bg-error text-on-error";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

const PROXY_SCHEMES = ["http", "https", "socks5"];
const PROXY_TYPES = ["datacenter", "residential", "mobile"];
const PROXY_ROTATIONS = ["sticky", "rotating"];

const EMPTY_PROXY: ProxyInput = {
  name: "", host: "", port: 8080, scheme: "http", type: "datacenter",
  provider: "", username: "", password: "", rotation: "sticky", priority: 100,
};

function ApiProxyPanel({ apiId }: { apiId: string }) {
  const [items, setItems] = useState<Proxy[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<ProxyInput>(EMPTY_PROXY);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await getApiProxies(apiId);
      setItems(r.items);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro ao carregar proxies");
    } finally {
      setLoading(false);
    }
  }, [apiId]);
  useEffect(() => { load(); }, [load]);

  const field = (k: keyof ProxyInput, v: string | number | null) =>
    setForm((f) => ({ ...f, [k]: v }));

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setErr(null);
    try {
      await createApiProxy(apiId, {
        ...form,
        provider: form.provider || null,
        username: form.username || null,
        password: form.password || null,
      });
      setForm(EMPTY_PROXY); setShowAdd(false); await load();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Falha ao criar proxy");
    } finally { setSaving(false); }
  }

  async function toggle(p: Proxy) {
    await updateApiProxy(apiId, p.id, { status: p.status === "active" ? "inactive" : "active" });
    await load();
  }
  async function remove(id: string) {
    if (!confirm("Remover este proxy?")) return;
    await deleteApiProxy(apiId, id); await load();
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-lg font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[20px]">lan</span> Proxies desta API
        </h4>
        <button type="button" onClick={() => { setForm(EMPTY_PROXY); setShowAdd((v) => !v); }}
          className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-bold text-xs hover:bg-surface-container-highest">
          {showAdd ? "Cancelar" : "+ Adicionar proxy"}
        </button>
      </div>
      {err && <p className="text-xs text-error">{err}</p>}

      {showAdd && (
        <form onSubmit={add} className="bg-surface-container-low rounded-xl p-4 grid grid-cols-3 gap-3">
          <PInput label="Nome" value={form.name} onChange={(v) => field("name", v)} required />
          <PInput label="Host" value={form.host} onChange={(v) => field("host", v)} required />
          <PInput label="Porta" type="number" value={String(form.port)} onChange={(v) => field("port", Number(v))} required />
          <PSelect label="Scheme" value={form.scheme!} options={PROXY_SCHEMES} onChange={(v) => field("scheme", v)} />
          <PSelect label="Tipo" value={form.type!} options={PROXY_TYPES} onChange={(v) => field("type", v)} />
          <PSelect label="Rotação" value={form.rotation!} options={PROXY_ROTATIONS} onChange={(v) => field("rotation", v)} />
          <PInput label="Usuário" value={form.username ?? ""} onChange={(v) => field("username", v)} />
          <PInput label="Senha" value={form.password ?? ""} onChange={(v) => field("password", v)} />
          <PInput label="Prioridade" type="number" value={String(form.priority)} onChange={(v) => field("priority", Number(v))} />
          <div className="col-span-3 flex justify-end">
            <button type="submit" disabled={saving}
              className="px-5 py-2 rounded-lg bg-primary text-white font-bold text-xs hover:opacity-90 disabled:opacity-50">
              {saving ? "Salvando…" : "Criar proxy"}
            </button>
          </div>
        </form>
      )}

      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
        {loading ? (
          <p className="py-6 text-center text-on-surface-variant text-sm">Carregando…</p>
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-on-surface-variant text-sm">Nenhum proxy nesta API.</p>
        ) : (
          <div className="divide-y divide-outline-variant/10">
            {items.map((p) => (
              <div key={p.id} className="grid grid-cols-[80px_1fr_120px_80px_44px] items-center gap-2 px-4 py-2.5 text-sm">
                <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${statusPill(p.status)}`}>{p.status}</span>
                <div className="min-w-0">
                  <p className="font-bold text-on-surface truncate">{p.name}</p>
                  <p className="text-xs text-on-surface-variant font-mono truncate">{p.scheme}://{p.host}:{p.port} · {p.type}</p>
                  {p.last_error && <p className="text-xs text-error truncate">⚠ {p.last_error}</p>}
                </div>
                <span className="text-xs text-on-surface-variant">prio {p.priority} · {p.rotation}</span>
                <button type="button" onClick={() => toggle(p)} className="text-xs font-bold text-primary hover:underline justify-self-start">
                  {p.status === "active" ? "Desativar" : "Ativar"}
                </button>
                <button type="button" onClick={() => remove(p.id)} className="text-on-surface-variant hover:text-error justify-self-end">
                  <span className="material-symbols-outlined text-[18px]">delete</span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const EMPTY_CAPTCHA: CaptchaInput = {
  name: "", provider: "", api_key: "", balance_usd: null, priority: 100,
};

function ApiCaptchaPanel({ apiId }: { apiId: string }) {
  const [items, setItems] = useState<Captcha[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<CaptchaInput>(EMPTY_CAPTCHA);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await getApiCaptchas(apiId);
      setItems(r.items);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro ao carregar captchas");
    } finally {
      setLoading(false);
    }
  }, [apiId]);
  useEffect(() => { load(); }, [load]);

  const field = (k: keyof CaptchaInput, v: string | number | null) =>
    setForm((f) => ({ ...f, [k]: v }));

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setErr(null);
    try {
      await createApiCaptcha(apiId, {
        ...form,
        provider: form.provider || null,
        api_key: form.api_key || null,
        balance_usd: form.balance_usd ?? null,
      });
      setForm(EMPTY_CAPTCHA); setShowAdd(false); await load();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Falha ao criar provedor");
    } finally { setSaving(false); }
  }

  async function toggle(c: Captcha) {
    await updateApiCaptcha(apiId, c.id, { status: c.status === "active" ? "inactive" : "active" });
    await load();
  }
  async function remove(id: string) {
    if (!confirm("Remover este provedor?")) return;
    await deleteApiCaptcha(apiId, id); await load();
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-lg font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[20px]">verified_user</span> Captcha desta API
        </h4>
        <button type="button" onClick={() => { setForm(EMPTY_CAPTCHA); setShowAdd((v) => !v); }}
          className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-bold text-xs hover:bg-surface-container-highest">
          {showAdd ? "Cancelar" : "+ Adicionar provedor"}
        </button>
      </div>
      {err && <p className="text-xs text-error">{err}</p>}

      {showAdd && (
        <form onSubmit={add} className="bg-surface-container-low rounded-xl p-4 grid grid-cols-3 gap-3">
          <PInput label="Nome" value={form.name} onChange={(v) => field("name", v)} required />
          <PInput label="Provedor" value={form.provider ?? ""} onChange={(v) => field("provider", v)} />
          <PInput label="API key" value={form.api_key ?? ""} onChange={(v) => field("api_key", v)} />
          <PInput label="Saldo (US$)" type="number" value={form.balance_usd != null ? String(form.balance_usd) : ""} onChange={(v) => field("balance_usd", v === "" ? null : Number(v))} />
          <PInput label="Prioridade" type="number" value={String(form.priority)} onChange={(v) => field("priority", Number(v))} />
          <div className="col-span-3 flex justify-end">
            <button type="submit" disabled={saving}
              className="px-5 py-2 rounded-lg bg-primary text-white font-bold text-xs hover:opacity-90 disabled:opacity-50">
              {saving ? "Salvando…" : "Criar provedor"}
            </button>
          </div>
        </form>
      )}

      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
        {loading ? (
          <p className="py-6 text-center text-on-surface-variant text-sm">Carregando…</p>
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-on-surface-variant text-sm">Nenhum provedor nesta API.</p>
        ) : (
          <div className="divide-y divide-outline-variant/10">
            {items.map((c) => (
              <div key={c.id} className="grid grid-cols-[80px_1fr_120px_80px_44px] items-center gap-2 px-4 py-2.5 text-sm">
                <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${statusPill(c.status)}`}>{c.status}</span>
                <div className="min-w-0">
                  <p className="font-bold text-on-surface truncate">{c.name}</p>
                  <p className="text-xs text-on-surface-variant truncate">{c.provider ?? "—"} · {c.has_api_key ? "chave ✓" : "sem chave"}</p>
                  {c.last_error && <p className="text-xs text-error truncate">⚠ {c.last_error}</p>}
                </div>
                <span className="text-xs text-on-surface-variant">
                  {c.balance_usd != null ? `US$ ${c.balance_usd.toFixed(2)}` : "saldo —"} · prio {c.priority}
                </span>
                <button type="button" onClick={() => toggle(c)} className="text-xs font-bold text-primary hover:underline justify-self-start">
                  {c.status === "active" ? "Desativar" : "Ativar"}
                </button>
                <button type="button" onClick={() => remove(c.id)} className="text-on-surface-variant hover:text-error justify-self-end">
                  <span className="material-symbols-outlined text-[18px]">delete</span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PInput({ label, value, onChange, type = "text", required = false }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-bold text-on-surface-variant">{label}</label>
      <input
        type={type} value={value} required={required}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-on-surface focus:outline-none focus:border-primary"
      />
    </div>
  );
}

function PSelect({ label, value, options, onChange }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-bold text-on-surface-variant">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-on-surface">
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
