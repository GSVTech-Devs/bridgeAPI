"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";
import { getMe } from "@/lib/api";
import { ThemeDropdown } from "@/components/ThemeDropdown";
import { UserMenu } from "@/components/UserMenu";

const navItems = [
  { href: "/admin", label: "Dashboard", icon: "dashboard" },
  { href: "/admin/clients", label: "Contas", icon: "group" },
  { href: "/admin/apis", label: "APIs", icon: "api" },
  { href: "/admin/permissions", label: "Permissões", icon: "vpn_key" },
  { href: "/admin/metrics", label: "Métricas", icon: "analytics" },
  { href: "/admin/usage", label: "Uso por Cliente", icon: "account_balance_wallet" },
  { href: "/admin/logs", label: "Logs de Erro", icon: "error" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLoginPage = pathname === "/admin/login";
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (isLoginPage) return;
    if (!getToken()) {
      router.push("/admin/login");
      return;
    }
    getMe()
      .then((me) => setEmail(me.email))
      .catch(() => {});
  }, [router, isLoginPage]);

  // A página de login do admin não usa o chrome (sidebar/header) do painel.
  if (isLoginPage) {
    return <>{children}</>;
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
      </aside>

      {/* Main content */}
      <div className="ml-64 flex-1 flex flex-col min-h-screen">
        {/* Top header */}
        <header className="sticky top-0 z-30 flex justify-between items-center px-8 h-16 bg-surface border-b border-outline-variant/10">
          <span className="text-xl font-black text-primary font-headline tracking-tight">Bridge API</span>
          <div className="flex items-center gap-3">
            {/* <button className="p-2 rounded-full hover:bg-surface-container-low transition-colors">
              <span className="material-symbols-outlined text-on-surface-variant text-[20px]">notifications</span>
            </button> */}
            <ThemeDropdown />
            <UserMenu email={email} logoutHref="/admin/login" />
          </div>
        </header>

        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
