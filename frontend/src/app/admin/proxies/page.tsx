"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getProxyPools, createProxyPool, deleteProxyPool,
  getProxies, createProxy, updateProxy, deleteProxy,
  getApis, assignProxyPool,
  type ProxyPool, type Proxy, type ProxyInput,
} from "@/lib/api";

type Api = { id: string; name: string; proxy_pool_id?: string | null };

const SCHEMES = ["http", "https", "socks5"];
const TYPES = ["datacenter", "residential", "mobile"];
const OWNERSHIPS = ["platform", "client"];
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
  ownership: "platform", provider: "", username: "", password: "",
  rotation: "sticky", session_ttl_s: null, priority: 100, pool_id: null,
};

export default function ProxiesPage() {
  const [pools, setPools] = useState<ProxyPool[]>([]);
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [apis, setApis] = useState<Api[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [poolName, setPoolName] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ProxyInput>(EMPTY);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    const [p, px, a] = await Promise.all([getProxyPools(), getProxies(), getApis()]);
    setPools(p.items);
    setProxies(px.items);
    setApis(a.items);
  }, []);

  useEffect(() => {
    refresh().catch((e) => setErr(String(e))).finally(() => setLoading(false));
  }, [refresh]);

  async function addPool(e: React.FormEvent) {
    e.preventDefault();
    if (!poolName.trim()) return;
    await createProxyPool(poolName.trim());
    setPoolName("");
    await refresh();
  }

  async function removePool(id: string) {
    if (!confirm("Remover este pool? Os proxies ficam sem pool.")) return;
    await deleteProxyPool(id);
    await refresh();
  }

  async function submitProxy(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      await createProxy({
        ...form,
        provider: form.provider || null,
        username: form.username || null,
        password: form.password || null,
        pool_id: form.pool_id || null,
      });
      setShowForm(false);
      setForm(EMPTY);
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Falha ao criar proxy");
    } finally {
      setSaving(false);
    }
  }

  async function toggleProxy(p: Proxy) {
    await updateProxy(p.id, { status: p.status === "active" ? "inactive" : "active" });
    await refresh();
  }

  async function moveProxy(p: Proxy, poolId: string) {
    await updateProxy(p.id, { pool_id: poolId || null });
    await refresh();
  }

  async function removeProxy(id: string) {
    if (!confirm("Remover este proxy?")) return;
    await deleteProxy(id);
    await refresh();
  }

  async function assign(apiId: string, poolId: string) {
    await assignProxyPool(apiId, poolId || null);
    await refresh();
  }

  const field = (k: keyof ProxyInput, v: string | number | null) =>
    setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="max-w-7xl mx-auto space-y-10">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            Proxies
          </h2>
          <p className="text-on-surface-variant font-medium">
            Pools de proxy, status/failover e atribuição por API.
          </p>
        </div>
        <button
          onClick={() => { setForm(EMPTY); setShowForm(true); }}
          className="px-5 py-2.5 rounded-xl bg-primary text-white font-bold text-sm hover:opacity-90"
        >
          + Novo proxy
        </button>
      </div>

      {err && <div className="bg-error-container/30 text-error rounded-lg px-4 py-3 text-sm">{err}</div>}

      {/* Pools */}
      <section className="space-y-3">
        <h3 className="text-lg font-bold text-on-surface">Pools</h3>
        <form onSubmit={addPool} className="flex gap-2">
          <input
            value={poolName}
            onChange={(e) => setPoolName(e.target.value)}
            placeholder="Nome do novo pool…"
            className="flex-1 px-4 py-2.5 rounded-lg bg-surface-container-lowest border border-outline-variant/20 text-sm text-on-surface focus:outline-none focus:border-primary"
          />
          <button type="submit" className="px-5 py-2.5 rounded-lg bg-surface-container-high text-on-surface font-bold text-sm hover:bg-surface-container-highest">
            Criar pool
          </button>
        </form>
        <div className="flex flex-wrap gap-2">
          {pools.map((p) => (
            <div key={p.id} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-low">
              <span className="font-bold text-sm text-on-surface">{p.name}</span>
              <span className="text-xs text-on-surface-variant">{p.proxy_count} proxies</span>
              <button onClick={() => removePool(p.id)} className="text-on-surface-variant hover:text-error">
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>
          ))}
          {pools.length === 0 && <p className="text-sm text-on-surface-variant">Nenhum pool ainda.</p>}
        </div>
      </section>

      {/* Proxies */}
      <section className="space-y-3">
        <h3 className="text-lg font-bold text-on-surface">Proxies</h3>
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
          {loading ? (
            <p className="py-12 text-center text-on-surface-variant text-sm">Carregando…</p>
          ) : proxies.length === 0 ? (
            <p className="py-12 text-center text-on-surface-variant text-sm">Nenhum proxy cadastrado.</p>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {proxies.map((p) => (
                <div key={p.id} className="grid grid-cols-[90px_1fr_160px_140px_90px_120px] items-center gap-3 px-5 py-3.5 text-sm">
                  <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${statusPill(p.status)}`}>
                    {p.status}
                  </span>
                  <div className="min-w-0">
                    <p className="font-bold text-on-surface truncate">{p.name}</p>
                    <p className="text-xs text-on-surface-variant font-mono truncate">
                      {p.scheme}://{p.host}:{p.port} · {p.type} · {p.ownership}
                      {p.provider ? ` · ${p.provider}` : ""}
                    </p>
                    {p.last_error && (
                      <p className="text-xs text-error truncate">⚠ {p.last_error}</p>
                    )}
                  </div>
                  <select
                    value={p.pool_id ?? ""}
                    onChange={(e) => moveProxy(p, e.target.value)}
                    className="px-2 py-1.5 rounded-lg bg-surface-container border border-outline-variant/20 text-xs text-on-surface"
                  >
                    <option value="">— sem pool —</option>
                    {pools.map((pool) => (
                      <option key={pool.id} value={pool.id}>{pool.name}</option>
                    ))}
                  </select>
                  <span className="text-xs text-on-surface-variant">prio {p.priority} · {p.rotation}</span>
                  <button
                    onClick={() => toggleProxy(p)}
                    className="text-xs font-bold text-primary hover:underline justify-self-start"
                  >
                    {p.status === "active" ? "Desativar" : "Ativar"}
                  </button>
                  <button
                    onClick={() => removeProxy(p.id)}
                    className="text-on-surface-variant hover:text-error justify-self-end"
                  >
                    <span className="material-symbols-outlined text-[20px]">delete</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Atribuição API → Pool */}
      <section className="space-y-3">
        <h3 className="text-lg font-bold text-on-surface">APIs → Pool</h3>
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden divide-y divide-outline-variant/10">
          {apis.length === 0 ? (
            <p className="py-10 text-center text-on-surface-variant text-sm">Nenhuma API cadastrada.</p>
          ) : (
            apis.map((api) => (
              <div key={api.id} className="flex items-center justify-between px-5 py-3 text-sm">
                <span className="font-medium text-on-surface">{api.name}</span>
                <select
                  value={api.proxy_pool_id ?? ""}
                  onChange={(e) => assign(api.id, e.target.value)}
                  className="px-3 py-1.5 rounded-lg bg-surface-container border border-outline-variant/20 text-xs text-on-surface"
                >
                  <option value="">— sem pool —</option>
                  {pools.map((pool) => (
                    <option key={pool.id} value={pool.id}>{pool.name}</option>
                  ))}
                </select>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Modal de criação de proxy */}
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
              <Select label="Propriedade" value={form.ownership!} options={OWNERSHIPS} onChange={(v) => field("ownership", v)} />
              <Select label="Rotação" value={form.rotation!} options={ROTATIONS} onChange={(v) => field("rotation", v)} />
              <Input label="Prioridade" type="number" value={String(form.priority)} onChange={(v) => field("priority", Number(v))} />
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold text-on-surface-variant">Pool</label>
                <select
                  value={form.pool_id ?? ""}
                  onChange={(e) => field("pool_id", e.target.value || null)}
                  className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-on-surface"
                >
                  <option value="">— sem pool —</option>
                  {pools.map((pool) => <option key={pool.id} value={pool.id}>{pool.name}</option>)}
                </select>
              </div>
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
