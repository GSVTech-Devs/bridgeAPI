"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getApis,
  getApiCaptchas, createApiCaptcha, updateApiCaptcha, deleteApiCaptcha,
  getCaptchaMonitor,
  type Captcha, type CaptchaInput, type CaptchaMonitorItem,
} from "@/lib/api";

type Api = { id: string; name: string; uses_captcha?: boolean };

function statusPill(s: string): string {
  switch (s) {
    case "active": return "bg-green-600 text-white";
    case "failing": return "bg-error text-on-error";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

const EMPTY: CaptchaInput = {
  name: "", provider: "", api_key: "", balance_usd: null, priority: 100,
};

export default function AdminCaptchaPage() {
  const [apis, setApis] = useState<Api[]>([]);
  const [apiId, setApiId] = useState<string>("");
  const [items, setItems] = useState<Captcha[]>([]);
  const [monitor, setMonitor] = useState<CaptchaMonitorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CaptchaInput>(EMPTY);
  const [saving, setSaving] = useState(false);

  const loadApis = useCallback(async () => {
    const [a, m] = await Promise.all([getApis(), getCaptchaMonitor()]);
    setApis(a.items);
    setMonitor(m.items);
    if (!apiId && a.items.length) setApiId(a.items[0].id);
  }, [apiId]);

  const loadItems = useCallback(async (id: string) => {
    if (!id) { setItems([]); return; }
    const c = await getApiCaptchas(id);
    setItems(c.items);
  }, []);

  useEffect(() => {
    loadApis().catch((e) => setErr(String(e))).finally(() => setLoading(false));
  }, [loadApis]);

  useEffect(() => {
    if (apiId) loadItems(apiId).catch((e) => setErr(String(e)));
  }, [apiId, loadItems]);

  async function refresh() {
    await Promise.all([loadItems(apiId), getCaptchaMonitor().then((m) => setMonitor(m.items))]);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      await createApiCaptcha(apiId, {
        ...form,
        provider: form.provider || null,
        api_key: form.api_key || null,
        balance_usd: form.balance_usd ?? null,
      });
      setShowForm(false);
      setForm(EMPTY);
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Falha ao criar provedor");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(c: Captcha) {
    await updateApiCaptcha(apiId, c.id, { status: c.status === "active" ? "inactive" : "active" });
    await refresh();
  }

  async function remove(id: string) {
    if (!confirm("Remover este provedor?")) return;
    await deleteApiCaptcha(apiId, id);
    await refresh();
  }

  const field = (k: keyof CaptchaInput, v: string | number | null) =>
    setForm((f) => ({ ...f, [k]: v }));

  const selectedApi = apis.find((a) => a.id === apiId);

  return (
    <div className="max-w-7xl mx-auto space-y-10">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            Captcha por API
          </h2>
          <p className="text-on-surface-variant font-medium">
            Provedores de captcha da plataforma para cada API. Saldo e status entram no monitoramento.
          </p>
        </div>
        {apiId && (
          <button
            onClick={() => { setForm(EMPTY); setShowForm(true); }}
            className="px-5 py-2.5 rounded-xl bg-primary text-white font-bold text-sm hover:opacity-90"
          >
            + Novo provedor
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
            {apis.map((a) => (
              <option key={a.id} value={a.id}>{a.name}{a.uses_captcha ? "" : " (não usa captcha)"}</option>
            ))}
          </select>
          {selectedApi && !selectedApi.uses_captcha && (
            <span className="text-xs text-on-surface-variant">⚠ Esta API está marcada como “não usa captcha”.</span>
          )}
        </div>

        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
          {loading ? (
            <p className="py-12 text-center text-on-surface-variant text-sm">Carregando…</p>
          ) : items.length === 0 ? (
            <p className="py-12 text-center text-on-surface-variant text-sm">Nenhum provedor nesta API.</p>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {items.map((c) => (
                <div key={c.id} className="grid grid-cols-[90px_1fr_130px_90px_120px] items-center gap-3 px-5 py-3.5 text-sm">
                  <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${statusPill(c.status)}`}>
                    {c.status}
                  </span>
                  <div className="min-w-0">
                    <p className="font-bold text-on-surface truncate">{c.name}</p>
                    <p className="text-xs text-on-surface-variant truncate">
                      {c.provider ?? "—"} · {c.has_api_key ? "chave ✓" : "sem chave"}
                    </p>
                    {c.last_error && <p className="text-xs text-error truncate">⚠ {c.last_error}</p>}
                  </div>
                  <span className="text-xs text-on-surface-variant">
                    {c.balance_usd != null ? `US$ ${c.balance_usd.toFixed(2)}` : "saldo —"} · prio {c.priority}
                  </span>
                  <button onClick={() => toggle(c)} className="text-xs font-bold text-primary hover:underline justify-self-start">
                    {c.status === "active" ? "Desativar" : "Ativar"}
                  </button>
                  <button onClick={() => remove(c.id)} className="text-on-surface-variant hover:text-error justify-self-end">
                    <span className="material-symbols-outlined text-[20px]">delete</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-lg font-bold text-on-surface">Monitoramento (todas as APIs)</h3>
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden divide-y divide-outline-variant/10">
          {monitor.length === 0 ? (
            <p className="py-10 text-center text-on-surface-variant text-sm">Nenhum provedor cadastrado.</p>
          ) : (
            monitor.map((m) => (
              <div key={m.id} className="grid grid-cols-[90px_1fr_130px_120px] items-center gap-3 px-5 py-3 text-sm">
                <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${statusPill(m.status)}`}>
                  {m.status}
                </span>
                <div className="min-w-0">
                  <p className="font-bold text-on-surface truncate">{m.name}</p>
                  <p className="text-xs text-on-surface-variant truncate">{m.provider ?? "—"} · {m.api_name}</p>
                  {m.last_error && <p className="text-xs text-error truncate">⚠ {m.last_error}</p>}
                </div>
                <span className="text-xs text-on-surface-variant">
                  {m.balance_usd != null ? `US$ ${m.balance_usd.toFixed(2)}` : "saldo —"}
                </span>
                <span className="text-xs text-on-surface-variant justify-self-end">
                  {m.account_id ? "cliente" : "plataforma"}
                </span>
              </div>
            ))
          )}
        </div>
      </section>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowForm(false)}>
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={submit}
            className="bg-surface-container-lowest rounded-2xl p-6 w-full max-w-md space-y-4"
          >
            <h3 className="text-xl font-bold text-on-surface">Novo provedor de captcha</h3>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Nome" value={form.name} onChange={(v) => field("name", v)} required />
              <Input label="Provedor" value={form.provider ?? ""} onChange={(v) => field("provider", v)} />
              <Input label="API key" value={form.api_key ?? ""} onChange={(v) => field("api_key", v)} />
              <Input label="Saldo (US$)" type="number" value={form.balance_usd != null ? String(form.balance_usd) : ""} onChange={(v) => field("balance_usd", v === "" ? null : Number(v))} />
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
