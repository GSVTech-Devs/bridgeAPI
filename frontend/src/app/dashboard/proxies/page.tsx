"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getCatalog,
  getClientApiProxies, createClientApiProxy, updateClientApiProxy, deleteClientApiProxy,
  type Proxy, type ProxyInput,
} from "@/lib/api";
import { useCapabilities } from "@/contexts/CapabilitiesContext";
import { CAP } from "@/lib/capabilities";

type Api = { id: string; name: string; uses_proxy?: boolean };

const SCHEMES = ["http", "https", "socks5"];
const TYPES = ["datacenter", "residential", "mobile"];
const ROTATIONS = ["sticky", "rotating"];

function statusPill(s: string): string {
  switch (s) {
    case "active": return "bg-green-600 text-white";
    case "failing": return "bg-error text-on-error";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

const EMPTY: ProxyInput = {
  name: "", host: "", port: 8080, scheme: "http", type: "datacenter",
  provider: "", username: "", password: "",
  rotation: "sticky", session_ttl_s: null, priority: 100,
};

export default function ClientProxiesPage() {
  const { can, loading: capsLoading } = useCapabilities();
  const allowed = can(CAP.PROXIES);

  const [apis, setApis] = useState<Api[]>([]);
  const [apiId, setApiId] = useState<string>("");
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [notEnabled, setNotEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ProxyInput>(EMPTY);
  const [saving, setSaving] = useState(false);

  const loadApis = useCallback(async () => {
    const c = await getCatalog();
    const usable = c.items.filter((a) => a.uses_proxy);
    setApis(usable);
    if (!apiId && usable.length) setApiId(usable[0].id);
  }, [apiId]);

  const loadProxies = useCallback(async (id: string) => {
    if (!id) { setProxies([]); return; }
    setNotEnabled(false);
    try {
      const px = await getClientApiProxies(id);
      setProxies(px.items);
    } catch {
      // 403 = o admin não habilitou autosserviço de proxy nesta API
      setProxies([]);
      setNotEnabled(true);
    }
  }, []);

  useEffect(() => {
    if (!allowed) { setLoading(false); return; }
    loadApis().catch((e) => setErr(String(e))).finally(() => setLoading(false));
  }, [loadApis, allowed]);

  useEffect(() => {
    if (apiId && allowed) loadProxies(apiId).catch((e) => setErr(String(e)));
  }, [apiId, allowed, loadProxies]);

  async function submitProxy(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      await createClientApiProxy(apiId, {
        ...form,
        provider: form.provider || null,
        username: form.username || null,
        password: form.password || null,
      });
      setShowForm(false);
      setForm(EMPTY);
      await loadProxies(apiId);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Falha ao criar proxy");
    } finally {
      setSaving(false);
    }
  }

  async function toggleProxy(p: Proxy) {
    await updateClientApiProxy(apiId, p.id, { status: p.status === "active" ? "inactive" : "active" });
    await loadProxies(apiId);
  }

  async function removeProxy(id: string) {
    if (!confirm("Remover este proxy?")) return;
    await deleteClientApiProxy(apiId, id);
    await loadProxies(apiId);
  }

  const field = (k: keyof ProxyInput, v: string | number | null) =>
    setForm((f) => ({ ...f, [k]: v }));

  if (!capsLoading && !allowed) {
    return (
      <div className="max-w-3xl mx-auto py-20 text-center">
        <span className="material-symbols-outlined text-5xl text-on-surface-variant">lock</span>
        <p className="mt-4 text-on-surface-variant">
          Você não tem acesso à gestão de proxies. Fale com o responsável da conta.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-10">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            Meus proxies
          </h2>
          <p className="text-on-surface-variant font-medium">
            Configure seus próprios proxies por API — quando o provedor da Bridge habilita isso.
          </p>
        </div>
        {apiId && !notEnabled && (
          <button
            onClick={() => { setForm(EMPTY); setShowForm(true); }}
            className="px-5 py-2.5 rounded-xl bg-primary text-white font-bold text-sm hover:opacity-90"
          >
            + Novo proxy
          </button>
        )}
      </div>

      {err && <div className="bg-error-container/30 text-error rounded-lg px-4 py-3 text-sm">{err}</div>}

      <section className="space-y-3">
        <div className="flex items-center gap-3">
          <label className="text-sm font-bold text-on-surface-variant">API:</label>
          <select
            value={apiId}
            onChange={(e) => setApiId(e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-on-surface"
          >
            {apis.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>

        {notEnabled ? (
          <p className="py-12 text-center text-on-surface-variant text-sm bg-surface-container-lowest rounded-xl border border-outline-variant/10">
            O provedor não habilitou a configuração do seu proxy nesta API.
          </p>
        ) : (
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
            {loading ? (
              <p className="py-12 text-center text-on-surface-variant text-sm">Carregando…</p>
            ) : apis.length === 0 ? (
              <p className="py-12 text-center text-on-surface-variant text-sm">Nenhuma API com proxy disponível.</p>
            ) : proxies.length === 0 ? (
              <p className="py-12 text-center text-on-surface-variant text-sm">Nenhum proxy seu nesta API ainda.</p>
            ) : (
              <div className="divide-y divide-outline-variant/10">
                {proxies.map((p) => (
                  <div key={p.id} className="grid grid-cols-[90px_1fr_140px_90px_120px] items-center gap-3 px-5 py-3.5 text-sm">
                    <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${statusPill(p.status)}`}>
                      {p.status}
                    </span>
                    <div className="min-w-0">
                      <p className="font-bold text-on-surface truncate">{p.name}</p>
                      <p className="text-xs text-on-surface-variant font-mono truncate">
                        {p.scheme}://{p.host}:{p.port} · {p.type}
                        {p.provider ? ` · ${p.provider}` : ""}
                      </p>
                      {p.last_error && <p className="text-xs text-error truncate">⚠ {p.last_error}</p>}
                    </div>
                    <span className="text-xs text-on-surface-variant">prio {p.priority} · {p.rotation}</span>
                    <button onClick={() => toggleProxy(p)} className="text-xs font-bold text-primary hover:underline justify-self-start">
                      {p.status === "active" ? "Desativar" : "Ativar"}
                    </button>
                    <button onClick={() => removeProxy(p.id)} className="text-on-surface-variant hover:text-error justify-self-end">
                      <span className="material-symbols-outlined text-[20px]">delete</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowForm(false)}>
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={submitProxy}
            className="bg-surface-container-lowest rounded-2xl p-6 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto"
          >
            <h3 className="text-xl font-bold text-on-surface">Novo proxy</h3>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Nome" value={form.name} onChange={(v) => field("name", v)} required />
              <Input label="Provedor" value={form.provider ?? ""} onChange={(v) => field("provider", v)} />
              <Input label="Host" value={form.host} onChange={(v) => field("host", v)} required />
              <Input label="Porta" type="number" value={String(form.port)} onChange={(v) => field("port", Number(v))} required />
              <Input label="Usuário" value={form.username ?? ""} onChange={(v) => field("username", v)} />
              <Input label="Senha" value={form.password ?? ""} onChange={(v) => field("password", v)} />
              <Select label="Scheme" value={form.scheme!} options={SCHEMES} onChange={(v) => field("scheme", v)} />
              <Select label="Tipo" value={form.type!} options={TYPES} onChange={(v) => field("type", v)} />
              <Select label="Rotação" value={form.rotation!} options={ROTATIONS} onChange={(v) => field("rotation", v)} />
              <Input label="Prioridade" type="number" value={String(form.priority)} onChange={(v) => field("priority", Number(v))} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 rounded-lg text-on-surface-variant font-bold text-sm hover:bg-surface-container">
                Cancelar
              </button>
              <button type="submit" disabled={saving} className="px-5 py-2 rounded-lg bg-primary text-white font-bold text-sm hover:opacity-90 disabled:opacity-50">
                {saving ? "Salvando…" : "Criar"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Input({ label, value, onChange, type = "text", required = false }: {
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

function Select({ label, value, options, onChange }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-bold text-on-surface-variant">{label}</label>
      <select
        value={value} onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-on-surface"
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
