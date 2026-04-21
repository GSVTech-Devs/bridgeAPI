"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getToken } from "@/lib/auth";
import { ThemeDropdown } from "@/components/ThemeDropdown";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { href: "/dashboard/catalog", label: "Catalog", icon: "api" },
  { href: "/dashboard/keys", label: "My Keys", icon: "vpn_key" },
  { href: "/dashboard/metrics", label: "Logs & Métricas", icon: "analytics" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
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
      <nav className="fixed left-0 top-0 h-screen w-64 bg-surface-container-low flex flex-col py-8 px-4 z-50">
        <div className="mb-10 px-4">
          <h1 className="text-xl font-black tracking-tight text-on-surface font-headline">Bridge API</h1>
          <p className="text-sm text-on-surface-variant mt-1">Developer Console</p>
        </div>

        <ul className="flex-1 space-y-2">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={
                    active
                      ? "flex items-center gap-3 px-4 py-3 rounded-full bg-surface-container-lowest text-primary font-bold border-r-4 border-primary transition-all"
                      : "flex items-center gap-3 px-4 py-3 rounded-full text-on-surface-variant hover:bg-surface transition-colors"
                  }
                >
                  <span
                    className="material-symbols-outlined text-[20px]"
                    style={active ? { fontVariationSettings: "'FILL' 1" } : undefined}
                  >
                    {item.icon}
                  </span>
                  <span className="text-sm">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="mt-auto space-y-2 border-t border-outline-variant/15 pt-4">
          <a
            href="#"
            className="flex items-center gap-3 px-4 py-2 rounded-full text-on-surface-variant hover:bg-surface transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">help_outline</span>
            <span className="text-sm">Help</span>
          </a>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-2 rounded-full text-on-surface-variant hover:bg-surface transition-colors w-full text-left"
          >
            <span className="material-symbols-outlined text-[20px]">logout</span>
            <span className="text-sm">Sair</span>
          </button>
        </div>
      </nav>

      {/* Main area */}
      <div className="ml-64 flex-1 flex flex-col min-h-screen">
        {/* Top header */}
        <header className="fixed top-0 right-0 left-64 z-40 bg-surface/80 backdrop-blur-md flex justify-between items-center px-8 h-16 shadow-[0_4px_20px_0_rgb(var(--color-on-background)/0.05)]">
          <div className="flex items-center bg-surface-container-low rounded-full px-4 py-2 w-72 border border-outline-variant/15 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-all">
            <span className="material-symbols-outlined text-on-surface-variant text-[18px] mr-2">search</span>
            <input
              className="bg-transparent border-none focus:ring-0 w-full text-sm text-on-surface outline-none"
              placeholder="Search resources..."
            />
          </div>
          <div className="flex items-center gap-3">
            <button className="text-on-surface-variant hover:bg-surface-container-low rounded-full p-2 transition-colors">
              <span className="material-symbols-outlined text-[20px]">notifications</span>
            </button>
            <ThemeDropdown />
            <div className="h-8 w-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-bold text-sm ml-1">
              U
            </div>
          </div>
        </header>

        <main className="mt-16 flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
