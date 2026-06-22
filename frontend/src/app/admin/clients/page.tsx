"use client";

import { useEffect, useState } from "react";
import {
  getAccounts,
  createIndividualUser,
  createCompany,
  blockAccount,
  unblockAccount,
  updateAccountCredentials,
} from "@/lib/api";
import { isValidPassword, PASSWORD_REQUIREMENTS_MESSAGE } from "@/lib/password";
import AccountUsersManager from "@/components/AccountUsersManager";

type Account = {
  id: string;
  name: string;
  type: "individual" | "company";
  status: string;
  owner_email: string | null;
};

const inputClass =
  "w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-2.5 text-sm text-on-surface focus:border-primary focus:ring-0 outline-none transition-all";

const statusConfig: Record<string, { dot: string; label: string }> = {
  active: { dot: "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]", label: "Ativa" },
  blocked: { dot: "bg-slate-400", label: "Bloqueada" },
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

function CreateAccountModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [mode, setMode] = useState<"individual" | "company">("individual");
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    company_name: "",
    owner_email: "",
    owner_password: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const password = mode === "individual" ? form.password : form.owner_password;
    if (!isValidPassword(password)) {
      setError(PASSWORD_REQUIREMENTS_MESSAGE);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (mode === "individual") {
        await createIndividualUser({
          name: form.name,
          email: form.email,
          password: form.password,
        });
      } else {
        await createCompany({
          company_name: form.company_name,
          owner_email: form.owner_email,
          owner_password: form.owner_password,
        });
      }
      onCreated();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao criar conta");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl p-8 shadow-xl">
        <h3 className="text-xl font-bold text-on-surface font-headline mb-1">Nova conta</h3>
        <p className="text-sm text-on-surface-variant mb-6">
          Crie um usuário avulso ou uma empresa com responsável.
        </p>

        {/* Mode toggle */}
        <div className="flex gap-2 mb-6 bg-surface-container-low rounded-lg p-1">
          <button
            type="button"
            onClick={() => setMode("individual")}
            className={`flex-1 py-2 rounded-md text-sm font-semibold transition-all ${
              mode === "individual" ? "bg-primary text-white" : "text-on-surface-variant"
            }`}
          >
            Usuário avulso
          </button>
          <button
            type="button"
            onClick={() => setMode("company")}
            className={`flex-1 py-2 rounded-md text-sm font-semibold transition-all ${
              mode === "company" ? "bg-primary text-white" : "text-on-surface-variant"
            }`}
          >
            Empresa
          </button>
        </div>

        {error && (
          <div role="alert" className="mb-4 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "individual" ? (
            <>
              <input
                aria-label="Nome"
                className={inputClass}
                placeholder="Nome do usuário"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                required
              />
              <input
                aria-label="Email"
                type="email"
                className={inputClass}
                placeholder="email@exemplo.com"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                required
              />
              <input
                aria-label="Senha"
                type="password"
                className={inputClass}
                placeholder="Senha inicial"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
                minLength={8}
                required
              />
              <p className="text-xs text-on-surface-variant -mt-2">
                {PASSWORD_REQUIREMENTS_MESSAGE}
              </p>
            </>
          ) : (
            <>
              <input
                aria-label="Nome da empresa"
                className={inputClass}
                placeholder="Nome da empresa"
                value={form.company_name}
                onChange={(e) => set("company_name", e.target.value)}
                required
              />
              <input
                aria-label="Email do responsável"
                type="email"
                className={inputClass}
                placeholder="responsavel@empresa.com"
                value={form.owner_email}
                onChange={(e) => set("owner_email", e.target.value)}
                required
              />
              <input
                aria-label="Senha do responsável"
                type="password"
                className={inputClass}
                placeholder="Senha inicial"
                value={form.owner_password}
                onChange={(e) => set("owner_password", e.target.value)}
                minLength={8}
                required
              />
              <p className="text-xs text-on-surface-variant -mt-2">
                {PASSWORD_REQUIREMENTS_MESSAGE}
              </p>
            </>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-lg bg-surface-container-high text-on-surface font-semibold text-sm hover:brightness-95 transition-all"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 rounded-lg bg-gradient-to-br from-primary to-primary-container text-white font-bold text-sm hover:scale-[1.02] transition-all disabled:opacity-60"
            >
              {loading ? "Criando…" : "Criar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ManageAccountModal({
  account,
  onClose,
  onUpdated,
}: {
  account: Account;
  onClose: () => void;
  onUpdated: (email: string) => void;
}) {
  const isCompany = account.type === "company";
  const [tab, setTab] = useState<"credentials" | "users">("credentials");
  const [email, setEmail] = useState(account.owner_email ?? "");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Fecha o modal com a tecla ESC. Modais aninhados (roles/usuários) capturam
  // o ESC antes deste handler, então só este fecha quando nenhum está aberto.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const trimmedEmail = email.trim();
    const emailChanged =
      trimmedEmail !== "" && trimmedEmail !== (account.owner_email ?? "");
    const data: { email?: string; password?: string } = {};
    if (emailChanged) data.email = trimmedEmail;
    if (password !== "") {
      if (!isValidPassword(password)) {
        setError(PASSWORD_REQUIREMENTS_MESSAGE);
        return;
      }
      data.password = password;
    }

    if (data.email === undefined && data.password === undefined) {
      setError("Altere o email ou a senha para salvar.");
      return;
    }

    setLoading(true);
    try {
      const res = await updateAccountCredentials(account.id, data);
      setPassword("");
      setSuccess("Credenciais atualizadas com sucesso.");
      onUpdated(res.owner_email);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao atualizar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className={`w-full bg-surface-container-lowest rounded-2xl p-8 shadow-xl max-h-[90vh] overflow-y-auto ${
          isCompany && tab === "users" ? "max-w-2xl" : "max-w-md"
        }`}
      >
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h3 className="text-xl font-bold text-on-surface font-headline mb-1">
              {isCompany ? "Gerenciar empresa" : "Gerenciar acesso"}
            </h3>
            <p className="text-sm text-on-surface-variant">
              {account.name} · {isCompany ? "Empresa" : "Avulso"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="-mr-2 -mt-2 p-2 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[22px]">close</span>
          </button>
        </div>

        {isCompany && (
          <div className="flex gap-2 mb-6 bg-surface-container-low rounded-lg p-1">
            <button
              type="button"
              onClick={() => setTab("credentials")}
              className={`flex-1 py-2 rounded-md text-sm font-semibold transition-all ${
                tab === "credentials" ? "bg-primary text-white" : "text-on-surface-variant"
              }`}
            >
              Credenciais
            </button>
            <button
              type="button"
              onClick={() => setTab("users")}
              className={`flex-1 py-2 rounded-md text-sm font-semibold transition-all ${
                tab === "users" ? "bg-primary text-white" : "text-on-surface-variant"
              }`}
            >
              Usuários
            </button>
          </div>
        )}

        {isCompany && tab === "users" ? (
          <AccountUsersManager accountId={account.id} />
        ) : (
          <>
        {error && (
          <div role="alert" className="mb-4 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
            {error}
          </div>
        )}
        {success && (
          <div role="status" className="mb-4 p-3 bg-tertiary-container rounded-lg text-on-tertiary-container text-sm">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Email de acesso
            </label>
            <input
              aria-label="Email de acesso"
              type="email"
              className={inputClass}
              placeholder="email@exemplo.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Nova senha
            </label>
            <input
              aria-label="Nova senha"
              type="password"
              className={inputClass}
              placeholder="Deixe em branco para manter"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p className="text-xs text-on-surface-variant mt-1.5">
              {PASSWORD_REQUIREMENTS_MESSAGE}
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-lg bg-surface-container-high text-on-surface font-semibold text-sm hover:brightness-95 transition-all"
            >
              Fechar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 rounded-lg bg-gradient-to-br from-primary to-primary-container text-white font-bold text-sm hover:scale-[1.02] transition-all disabled:opacity-60"
            >
              {loading ? "Salvando…" : "Salvar"}
            </button>
          </div>
        </form>
          </>
        )}
      </div>
    </div>
  );
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [managing, setManaging] = useState<Account | null>(null);

  async function load() {
    try {
      const data = await getAccounts();
      setAccounts(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleBlock(id: string) {
    setActionLoading(id + "-block");
    try {
      await blockAccount(id);
      setAccounts((prev) => prev.map((a) => (a.id === id ? { ...a, status: "blocked" } : a)));
    } finally {
      setActionLoading(null);
    }
  }

  async function handleUnblock(id: string) {
    setActionLoading(id + "-unblock");
    try {
      await unblockAccount(id);
      setAccounts((prev) => prev.map((a) => (a.id === id ? { ...a, status: "active" } : a)));
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {showCreate && (
        <CreateAccountModal onClose={() => setShowCreate(false)} onCreated={load} />
      )}

      {managing && (
        <ManageAccountModal
          account={managing}
          onClose={() => setManaging(null)}
          onUpdated={(email) =>
            setAccounts((prev) =>
              prev.map((a) =>
                a.id === managing.id ? { ...a, owner_email: email } : a
              )
            )
          }
        />
      )}

      <div className="flex items-end justify-between gap-6">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline">Contas</h2>
          <p className="text-on-surface-variant max-w-md">
            Gerencie contas avulsas e empresas, e controle o acesso à plataforma.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-br from-primary to-primary-container text-white rounded-lg font-bold text-sm hover:scale-[1.02] transition-all shadow-sm"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          Nova conta
        </button>
      </div>

      <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
        {loading && <Spinner />}
        {error && <div role="alert" className="p-6 text-error bg-error-container/20">{error}</div>}

        {!loading && !error && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low/50">
                  {["Conta", "Tipo", "Acesso", "Status", "Ações"].map((h) => (
                    <th key={h} className="px-6 py-4 text-xs font-bold text-outline uppercase tracking-widest">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {accounts.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center py-12 text-on-surface-variant">
                      Nenhuma conta cadastrada
                    </td>
                  </tr>
                )}
                {accounts.map((a) => {
                  const cfg = statusConfig[a.status] ?? { dot: "bg-outline", label: a.status };
                  const initials = a.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
                  return (
                    <tr key={a.id} className="hover:bg-surface-container-low/20 transition-colors group">
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-secondary-fixed flex items-center justify-center text-secondary font-bold text-sm">
                            {initials}
                          </div>
                          <span className="text-sm font-bold text-on-surface">{a.name}</span>
                        </div>
                      </td>
                      <td className="px-6 py-5 text-sm text-outline">
                        {a.type === "company" ? "Empresa" : "Avulso"}
                      </td>
                      <td className="px-6 py-5 text-sm text-on-surface-variant">
                        {a.owner_email ?? "—"}
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-1.5">
                          <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
                          <span className="text-sm font-medium text-on-surface">{cfg.label}</span>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => setManaging(a)}
                            className="px-3 py-1 bg-surface-container-high text-on-surface rounded-md text-xs font-bold hover:brightness-95 transition-all"
                          >
                            Gerenciar
                          </button>
                          {a.status === "active" && (
                            <button
                              onClick={() => handleBlock(a.id)}
                              disabled={actionLoading === a.id + "-block"}
                              className="px-3 py-1 bg-error-container text-on-error-container rounded-md text-xs font-bold hover:brightness-95 transition-all disabled:opacity-50"
                            >
                              {actionLoading === a.id + "-block" ? "…" : "Bloquear"}
                            </button>
                          )}
                          {a.status === "blocked" && (
                            <button
                              onClick={() => handleUnblock(a.id)}
                              disabled={actionLoading === a.id + "-unblock"}
                              className="px-3 py-1 bg-tertiary text-white rounded-md text-xs font-bold shadow-sm hover:brightness-110 transition-all disabled:opacity-50"
                            >
                              {actionLoading === a.id + "-unblock" ? "…" : "Desbloquear"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
