"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getToken } from "@/lib/auth";
import { ThemeDropdown } from "@/components/ThemeDropdown";

const navItems = [
  { href: "/admin", label: "Dashboard", icon: "dashboard" },
  { href: "/admin/clients", label: "Clientes", icon: "group" },
  { href: "/admin/apis", label: "APIs", icon: "api" },
  { href: "/admin/permissions", label: "Permissões", icon: "vpn_key" },
  { href: "/admin/metrics", label: "Métricas", icon: "analytics" },
  { href: "/admin/usage", label: "Uso por Cliente", icon: "account_balance_wallet" },
  { href: "/admin/logs", label: "Logs de Erro", icon: "error" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
    }
  }, [router]);

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  return (
    <div className="flex min-h-screen bg-surface text-on-surface font-body">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-screen w-64 bg-surface-container-low flex flex-col py-6 z-40">
        <div className="px-8 mb-10">
          <h1 className="text-lg font-bold text-on-surface font-headline">GSV Tech</h1>
          <p className="text-[10px] uppercase tracking-widest text-primary opacity-70 mt-0.5">Developer Portal</p>
        </div>

        <nav className="flex-1 space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={
                  active
                    ? "flex items-center gap-3 bg-surface-container-lowest text-primary font-bold rounded-l-full ml-4 shadow-sm px-6 py-3 transition-all"
                    : "flex items-center gap-3 text-on-surface-variant hover:text-primary px-6 py-3 hover:bg-surface transition-all"
                }
              >
                <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                <span className="text-sm">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto space-y-1 px-2">
          <a
            href="#"
            className="flex items-center gap-3 text-on-surface-variant hover:text-primary px-6 py-3 transition-all"
          >
            <span className="material-symbols-outlined text-[20px]">help</span>
            <span className="text-sm">Suporte</span>
          </a>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 text-on-surface-variant hover:text-error px-6 py-3 transition-all w-full text-left"
          >
            <span className="material-symbols-outlined text-[20px]">logout</span>
            <span className="text-sm">Sair</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="ml-64 flex-1 flex flex-col min-h-screen">
        {/* Top header */}
        <header className="sticky top-0 z-30 flex justify-between items-center px-8 h-16 bg-surface border-b border-outline-variant/10">
          <span className="text-xl font-black text-primary font-headline tracking-tight">Bridge API</span>
          <div className="flex items-center gap-3">
            <button className="p-2 rounded-full hover:bg-surface-container-low transition-colors">
              <span className="material-symbols-outlined text-on-surface-variant text-[20px]">notifications</span>
            </button>
            <ThemeDropdown />
            <div className="h-8 w-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-bold text-sm ml-1">
              A
            </div>
          </div>
        </header>

        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
