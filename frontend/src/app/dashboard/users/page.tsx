"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getRoles,
  createRole,
  updateRole,
  deleteRole,
  getMembers,
  createMember,
  updateMember,
  deleteMember,
  type Role,
  type Member,
} from "@/lib/api";
import { ASSIGNABLE_CAPABILITIES, CAP } from "@/lib/capabilities";
import { isValidPassword, PASSWORD_REQUIREMENTS_MESSAGE } from "@/lib/password";
import { useCapabilities } from "@/contexts/CapabilitiesContext";

const inputClass =
  "w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-2.5 text-sm text-on-surface focus:border-primary focus:ring-0 outline-none transition-all";

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

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
        checked ? "bg-primary" : "bg-surface-container-high"
      }`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform mt-0.5 ${
          checked ? "translate-x-5" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function capLabel(value: string): string {
  return ASSIGNABLE_CAPABILITIES.find((c) => c.value === value)?.label ?? value;
}

// ---------------------------------------------------------------------------
// Modal de role
// ---------------------------------------------------------------------------
function RoleModal({
  role,
  onClose,
  onSaved,
}: {
  role: Role | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(role?.name ?? "");
  const [caps, setCaps] = useState<Set<string>>(
    new Set(role?.capabilities ?? [])
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleCap(value: string, on: boolean) {
    setCaps((prev) => {
      const next = new Set(prev);
      if (on) next.add(value);
      else next.delete(value);
      // "rotacionar chaves" pressupõe "ver chaves".
      if (value === CAP.KEYS_ROTATE && on) next.add(CAP.API_KEYS);
      if (value === CAP.API_KEYS && !on) next.delete(CAP.KEYS_ROTATE);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Informe um nome para a role.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = { name: name.trim(), capabilities: Array.from(caps) };
      if (role) await updateRole(role.id, payload);
      else await createRole(payload);
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao salvar role");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg bg-surface-container-lowest rounded-2xl p-8 shadow-xl max-h-[90vh] overflow-y-auto">
        <h3 className="text-xl font-bold text-on-surface font-headline mb-1">
          {role ? "Editar role" : "Nova role"}
        </h3>
        <p className="text-sm text-on-surface-variant mb-6">
          Defina o nome e as permissões de acesso desta role.
        </p>

        {error && (
          <div role="alert" className="mb-4 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Nome da role
            </label>
            <input
              aria-label="Nome da role"
              className={inputClass}
              placeholder="Ex.: Financeiro, Dev, Gerência"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-bold text-outline uppercase tracking-widest">
              Permissões
            </label>
            {ASSIGNABLE_CAPABILITIES.map((cap) => (
              <div
                key={cap.value}
                className="flex items-center justify-between gap-4 p-3 bg-surface-container-low rounded-lg"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="material-symbols-outlined text-primary text-[20px]">
                    {cap.icon}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-on-surface">{cap.label}</p>
                    <p className="text-xs text-on-surface-variant">{cap.description}</p>
                  </div>
                </div>
                <Toggle
                  checked={caps.has(cap.value)}
                  onChange={(on) => toggleCap(cap.value, on)}
                />
              </div>
            ))}
          </div>

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
              {loading ? "Salvando…" : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal de membro
// ---------------------------------------------------------------------------
function MemberModal({
  member,
  roles,
  onClose,
  onSaved,
}: {
  member: Member | null;
  roles: Role[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [email, setEmail] = useState(member?.email ?? "");
  const [password, setPassword] = useState("");
  const [roleId, setRoleId] = useState(member?.role_id ?? roles[0]?.id ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (member) {
      // edição: senha opcional
      const data: { email?: string; password?: string; role_id?: string } = {};
      const trimmed = email.trim();
      if (trimmed && trimmed !== member.email) data.email = trimmed;
      if (roleId && roleId !== member.role_id) data.role_id = roleId;
      if (password) {
        if (!isValidPassword(password)) {
          setError(PASSWORD_REQUIREMENTS_MESSAGE);
          return;
        }
        data.password = password;
      }
      if (Object.keys(data).length === 0) {
        setError("Altere algum campo para salvar.");
        return;
      }
      setLoading(true);
      try {
        await updateMember(member.id, data);
        onSaved();
        onClose();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Erro ao salvar usuário");
      } finally {
        setLoading(false);
      }
      return;
    }

    // criação
    if (!roleId) {
      setError("Selecione uma role.");
      return;
    }
    if (!isValidPassword(password)) {
      setError(PASSWORD_REQUIREMENTS_MESSAGE);
      return;
    }
    setLoading(true);
    try {
      await createMember({ email: email.trim(), password, role_id: roleId });
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao criar usuário");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl p-8 shadow-xl">
        <h3 className="text-xl font-bold text-on-surface font-headline mb-1">
          {member ? "Editar usuário" : "Novo usuário"}
        </h3>
        <p className="text-sm text-on-surface-variant mb-6">
          {member
            ? "Atualize o email, a senha ou a role do usuário."
            : "Crie um sub-usuário e atribua uma role."}
        </p>

        {error && (
          <div role="alert" className="mb-4 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Email
            </label>
            <input
              aria-label="Email"
              type="email"
              className={inputClass}
              placeholder="usuario@empresa.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              {member ? "Nova senha" : "Senha inicial"}
            </label>
            <input
              aria-label="Senha"
              type="password"
              className={inputClass}
              placeholder={member ? "Deixe em branco para manter" : "Senha inicial"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={member ? undefined : 8}
              required={!member}
            />
            <p className="text-xs text-on-surface-variant mt-1.5">
              {PASSWORD_REQUIREMENTS_MESSAGE}
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Role
            </label>
            <select
              aria-label="Role"
              className={inputClass}
              value={roleId}
              onChange={(e) => setRoleId(e.target.value)}
              required
            >
              <option value="" disabled>
                Selecione uma role
              </option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>

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
              {loading ? "Salvando…" : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Página
// ---------------------------------------------------------------------------
export default function UsersPage() {
  const router = useRouter();
  const { loading: capsLoading, isOwner, accountType, can } = useCapabilities();
  // Owner OU gerente delegado (membro com a capability MEMBERS), só em empresas.
  const canManage = accountType === "company" && (isOwner || can(CAP.MEMBERS));

  const [roles, setRoles] = useState<Role[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [roleModal, setRoleModal] = useState<{ open: boolean; role: Role | null }>({
    open: false,
    role: null,
  });
  const [memberModal, setMemberModal] = useState<{ open: boolean; member: Member | null }>({
    open: false,
    member: null,
  });
  const [actionError, setActionError] = useState<string | null>(null);

  // Guard: owner da empresa ou gerente delegado (capability MEMBERS).
  useEffect(() => {
    if (!capsLoading && !canManage) {
      router.replace("/dashboard");
    }
  }, [capsLoading, canManage, router]);

  async function load() {
    try {
      const [rolesData, membersData] = await Promise.all([getRoles(), getMembers()]);
      setRoles(rolesData.items);
      setMembers(membersData.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!capsLoading && canManage) load();
  }, [capsLoading, canManage]);

  async function handleDeleteRole(role: Role) {
    setActionError(null);
    if (!confirm(`Excluir a role "${role.name}"?`)) return;
    try {
      await deleteRole(role.id);
      load();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Erro ao excluir role");
    }
  }

  async function handleDeleteMember(member: Member) {
    setActionError(null);
    if (!confirm(`Excluir o usuário "${member.email}"?`)) return;
    try {
      await deleteMember(member.id);
      load();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Erro ao excluir usuário");
    }
  }

  if (capsLoading || !canManage) {
    return <Spinner />;
  }

  return (
    <div className="max-w-6xl mx-auto space-y-10">
      {roleModal.open && (
        <RoleModal
          role={roleModal.role}
          onClose={() => setRoleModal({ open: false, role: null })}
          onSaved={load}
        />
      )}
      {memberModal.open && (
        <MemberModal
          member={memberModal.member}
          roles={roles}
          onClose={() => setMemberModal({ open: false, member: null })}
          onSaved={load}
        />
      )}

      <div>
        <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline">Usuários</h2>
        <p className="text-on-surface-variant mt-1 max-w-xl">
          Crie roles com permissões específicas e adicione sub-usuários à sua empresa.
        </p>
      </div>

      {error && (
        <div role="alert" className="p-4 bg-error-container text-on-error-container rounded-xl text-sm">
          {error}
        </div>
      )}
      {actionError && (
        <div role="alert" className="p-4 bg-error-container text-on-error-container rounded-xl text-sm">
          {actionError}
        </div>
      )}

      {loading ? (
        <Spinner />
      ) : (
        <>
          {/* Roles */}
          <section className="space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <h3 className="font-headline text-xl font-bold text-on-surface">Roles</h3>
                <p className="text-sm text-on-surface-variant mt-0.5">
                  Conjuntos de permissões reutilizáveis.
                </p>
              </div>
              <button
                onClick={() => setRoleModal({ open: true, role: null })}
                className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-br from-primary to-primary-container text-white rounded-lg font-bold text-sm hover:scale-[1.02] transition-all shadow-sm"
              >
                <span className="material-symbols-outlined text-sm">add</span>
                Nova role
              </button>
            </div>

            {roles.length === 0 ? (
              <div className="text-center py-12 text-on-surface-variant bg-surface-container-lowest rounded-xl">
                <span className="material-symbols-outlined text-4xl mb-2 block opacity-40">badge</span>
                Nenhuma role criada ainda. Crie a primeira para adicionar usuários.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {roles.map((role) => (
                  <div
                    key={role.id}
                    className="bg-surface-container-lowest rounded-xl border border-outline-variant/15 p-5"
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div>
                        <h4 className="font-bold text-on-surface">{role.name}</h4>
                        <p className="text-xs text-on-surface-variant mt-0.5">
                          {role.member_count} usuário{role.member_count !== 1 ? "s" : ""}
                        </p>
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => setRoleModal({ open: true, role })}
                          title="Editar"
                          className="p-2 rounded-lg hover:bg-surface-container-high text-on-surface-variant transition-colors"
                        >
                          <span className="material-symbols-outlined text-[18px]">edit</span>
                        </button>
                        <button
                          onClick={() => handleDeleteRole(role)}
                          title="Excluir"
                          className="p-2 rounded-lg hover:bg-error-container text-on-surface-variant hover:text-error transition-colors"
                        >
                          <span className="material-symbols-outlined text-[18px]">delete</span>
                        </button>
                      </div>
                    </div>
                    {role.capabilities.length === 0 ? (
                      <span className="text-xs text-on-surface-variant italic">Sem permissões</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {role.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary font-medium"
                          >
                            {capLabel(cap)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Membros */}
          <section className="space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <h3 className="font-headline text-xl font-bold text-on-surface">Usuários da empresa</h3>
                <p className="text-sm text-on-surface-variant mt-0.5">
                  Sub-usuários com acesso ao portal.
                </p>
              </div>
              <button
                onClick={() => setMemberModal({ open: true, member: null })}
                disabled={roles.length === 0}
                title={roles.length === 0 ? "Crie uma role antes" : undefined}
                className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-br from-primary to-primary-container text-white rounded-lg font-bold text-sm hover:scale-[1.02] transition-all shadow-sm disabled:opacity-50 disabled:hover:scale-100"
              >
                <span className="material-symbols-outlined text-sm">person_add</span>
                Novo usuário
              </button>
            </div>

            <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-surface-container-low/50">
                      {["Email", "Role", "Criado em", "Ações"].map((h) => (
                        <th key={h} className="px-6 py-4 text-xs font-bold text-outline uppercase tracking-widest">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/10">
                    {members.length === 0 && (
                      <tr>
                        <td colSpan={4} className="text-center py-12 text-on-surface-variant">
                          Nenhum usuário cadastrado
                        </td>
                      </tr>
                    )}
                    {members.map((m) => (
                      <tr key={m.id} className="hover:bg-surface-container-low/20 transition-colors group">
                        <td className="px-6 py-4 text-sm font-medium text-on-surface">{m.email}</td>
                        <td className="px-6 py-4 text-sm text-on-surface-variant">
                          {m.role_name ?? "—"}
                        </td>
                        <td className="px-6 py-4 text-sm text-outline">
                          {new Date(m.created_at).toLocaleDateString("pt-BR")}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => setMemberModal({ open: true, member: m })}
                              className="px-3 py-1 bg-surface-container-high text-on-surface rounded-md text-xs font-bold hover:brightness-95 transition-all"
                            >
                              Editar
                            </button>
                            <button
                              onClick={() => handleDeleteMember(m)}
                              className="px-3 py-1 bg-error-container text-on-error-container rounded-md text-xs font-bold hover:brightness-95 transition-all"
                            >
                              Excluir
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
