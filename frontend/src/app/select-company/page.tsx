"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getPortalCompanies, selectCompany, type CompanyOption } from "@/lib/api";
import { clearAuth, getToken, saveAuthFromToken } from "@/lib/auth";

export default function SelectCompanyPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    getPortalCompanies()
      .then((res) => setCompanies(res.companies))
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erro ao carregar empresas")
      )
      .finally(() => setLoading(false));
  }, [router]);

  async function handleSelect(accountId: string) {
    setSelecting(accountId);
    setError(null);
    try {
      const scoped = await selectCompany(accountId);
      saveAuthFromToken(scoped.access_token);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Não foi possível acessar a empresa");
      setSelecting(null);
    }
  }

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  return (
    <div className="bg-surface font-body text-on-surface min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-1/4 -right-1/4 w-[800px] h-[800px] bg-surface-container-high rounded-full blur-[120px] opacity-40" />
        <div className="absolute -bottom-1/4 -left-1/4 w-[600px] h-[600px] bg-primary-fixed blur-[100px] opacity-30" />
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Header */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 mb-4 bg-surface-container-lowest rounded-xl shadow-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-4xl">apartment</span>
          </div>
          <h1 className="font-headline text-3xl font-extrabold tracking-tight text-on-background">
            Escolha a empresa
          </h1>
          <p className="text-on-surface-variant font-medium mt-1">
            Você tem acesso a mais de uma empresa
          </p>
        </div>

        {/* Card */}
        <div className="glass-panel bg-surface-container-lowest p-8 rounded-xl shadow-[0_4px_20px_0_rgba(7,30,39,0.05),0_12px_40px_-10px_rgba(43,91,181,0.08)]">
          {error && (
            <div
              role="alert"
              className="mb-6 p-3 bg-error-container rounded-lg text-on-error-container text-sm flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[18px]">error</span>
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-10 text-on-surface-variant">
              <svg className="animate-spin w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Carregando…
            </div>
          ) : companies.length === 0 ? (
            <p className="text-center text-on-surface-variant py-6 text-sm">
              Nenhuma empresa ativa disponível. Contate o administrador.
            </p>
          ) : (
            <ul className="space-y-3">
              {companies.map((c) => (
                <li key={c.account_id}>
                  <button
                    onClick={() => handleSelect(c.account_id)}
                    disabled={selecting !== null}
                    className="w-full flex items-center gap-4 p-4 rounded-lg bg-surface-container-low border border-outline-variant/20 hover:border-primary hover:bg-surface-container transition-all text-left disabled:opacity-60"
                  >
                    <span className="h-10 w-10 shrink-0 rounded-full bg-primary text-on-primary flex items-center justify-center font-bold">
                      {c.name.trim().charAt(0).toUpperCase() || "?"}
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm font-bold text-on-surface truncate">
                        {c.name}
                      </span>
                      <span className="block text-xs text-on-surface-variant capitalize">
                        {c.type === "company" ? "Empresa" : "Conta"} · {c.role === "owner" ? "Responsável" : "Membro"}
                      </span>
                    </span>
                    {selecting === c.account_id ? (
                      <svg className="animate-spin w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                      </svg>
                    ) : (
                      <span className="material-symbols-outlined text-on-surface-variant">chevron_right</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <button
            onClick={handleLogout}
            className="mt-6 flex items-center justify-center gap-2 w-full py-2.5 text-sm text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">logout</span>
            Sair
          </button>
        </div>
      </div>

      {/* Bottom gradient bar */}
      <div className="fixed bottom-0 left-0 right-0 h-1.5 primary-gradient opacity-80" />
    </div>
  );
}
