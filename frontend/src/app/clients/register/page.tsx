"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { registerClient } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (form.password !== form.confirm) {
      setError("As senhas não coincidem.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await registerClient({ name: form.name, email: form.email, password: form.password });
      setSuccess(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao cadastrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-surface min-h-screen flex items-center justify-center p-4 sm:p-8 font-body text-on-surface antialiased">
      <main className="w-full max-w-[480px] bg-surface-container-lowest p-8 sm:p-12 rounded-xl border border-outline-variant/10">

        {/* Brand Header */}
        <header className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-lg bg-surface-container-low text-primary mb-5">
            <span className="material-symbols-outlined text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>api</span>
          </div>
          <h1 className="font-headline text-3xl font-extrabold tracking-tight text-on-surface mb-2">
            Criar Conta
          </h1>
          <p className="font-body text-sm text-on-surface-variant">
            Junte-se à Bridge API por GSV Tech
          </p>
        </header>

        {success ? (
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-lg bg-surface-container-low text-primary mb-5">
              <span className="material-symbols-outlined text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
            </div>
            <h2 className="font-headline text-xl font-bold text-on-surface mb-3">Cadastro realizado!</h2>
            <p className="text-sm text-on-surface-variant mb-8">
              Sua conta foi criada e está <strong className="text-on-surface">pendente de aprovação</strong> pelo administrador. Você receberá acesso assim que for aprovado.
            </p>
            <button
              onClick={() => router.push("/login")}
              className="w-full bg-gradient-to-br from-primary to-primary-container hover:from-primary-container hover:to-primary text-white font-label font-semibold text-base py-4 rounded-xl transition-all duration-300 shadow-[0_8px_30px_-10px_rgba(43,91,181,0.3)] active:scale-[0.98] flex items-center justify-center gap-2"
            >
              Ir para o login
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
            </button>
          </div>
        ) : (
          <>
            {error && (
              <div role="alert" className="mb-6 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Nome Completo */}
              <div>
                <label htmlFor="name" className="block font-label text-sm font-medium text-on-surface mb-1.5">
                  Nome Completo
                </label>
                <div className="relative flex items-center border border-outline-variant/30 bg-surface-container-lowest rounded-xl transition-all duration-200 focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(43,91,181,0.1)]">
                  <span className="material-symbols-outlined text-outline ml-4 absolute pointer-events-none">person</span>
                  <input
                    id="name"
                    type="text"
                    className="w-full bg-transparent border-none py-3.5 pl-12 pr-4 text-on-surface font-body placeholder:text-outline/70 focus:ring-0 outline-none rounded-xl"
                    placeholder="Seu nome completo"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    required
                  />
                </div>
              </div>

              {/* E-mail */}
              <div>
                <label htmlFor="email" className="block font-label text-sm font-medium text-on-surface mb-1.5">
                  E-mail Corporativo
                </label>
                <div className="relative flex items-center border border-outline-variant/30 bg-surface-container-lowest rounded-xl transition-all duration-200 focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(43,91,181,0.1)]">
                  <span className="material-symbols-outlined text-outline ml-4 absolute pointer-events-none">mail</span>
                  <input
                    id="email"
                    type="email"
                    className="w-full bg-transparent border-none py-3.5 pl-12 pr-4 text-on-surface font-body placeholder:text-outline/70 focus:ring-0 outline-none rounded-xl"
                    placeholder="nome@suaempresa.com.br"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    required
                  />
                </div>
              </div>

              {/* Senha */}
              <div>
                <label htmlFor="password" className="block font-label text-sm font-medium text-on-surface mb-1.5">
                  Senha
                </label>
                <div className="relative flex items-center border border-outline-variant/30 bg-surface-container-lowest rounded-xl transition-all duration-200 focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(43,91,181,0.1)]">
                  <span className="material-symbols-outlined text-outline ml-4 absolute pointer-events-none">lock</span>
                  <input
                    id="password"
                    type="password"
                    className="w-full bg-transparent border-none py-3.5 pl-12 pr-4 text-on-surface font-body placeholder:text-outline/70 focus:ring-0 outline-none rounded-xl"
                    placeholder="Mínimo 8 caracteres"
                    value={form.password}
                    onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                    required
                    minLength={8}
                  />
                </div>
              </div>

              {/* Confirmar Senha */}
              <div>
                <label htmlFor="confirm" className="block font-label text-sm font-medium text-on-surface mb-1.5">
                  Confirme sua senha
                </label>
                <div className="relative flex items-center border border-outline-variant/30 bg-surface-container-lowest rounded-xl transition-all duration-200 focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(43,91,181,0.1)]">
                  <span className="material-symbols-outlined text-outline ml-4 absolute pointer-events-none">lock_reset</span>
                  <input
                    id="confirm"
                    type="password"
                    className="w-full bg-transparent border-none py-3.5 pl-12 pr-4 text-on-surface font-body placeholder:text-outline/70 focus:ring-0 outline-none rounded-xl"
                    placeholder="Repita sua senha"
                    value={form.confirm}
                    onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
                    required
                  />
                </div>
              </div>

              {/* Submit */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-br from-primary to-primary-container hover:from-primary-container hover:to-primary text-white font-label font-semibold text-base py-4 rounded-xl transition-all duration-300 shadow-[0_8px_30px_-10px_rgba(43,91,181,0.3)] active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-70"
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                      </svg>
                      Cadastrando…
                    </>
                  ) : (
                    <>
                      Criar Conta
                      <span className="material-symbols-outlined text-sm font-bold">arrow_forward</span>
                    </>
                  )}
                </button>
              </div>
            </form>

            <footer className="mt-8 pt-6 border-t border-surface-container-low text-center">
              <p className="font-body text-sm text-on-surface-variant">
                Já tem uma conta?{" "}
                <Link href="/login" className="font-medium text-primary hover:text-primary-container transition-colors duration-200">
                  Entrar
                </Link>
              </p>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
