"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";
import { ThemeDropdown } from "@/components/ThemeDropdown";
import { UserMenu } from "@/components/UserMenu";
import { BrandThemeStyle } from "@/components/BrandThemeStyle";
import { CAP } from "@/lib/capabilities";
import {
  CapabilitiesProvider,
  useCapabilities,
} from "@/contexts/CapabilitiesContext";

type NavItem = { href: string; label: string; icon: string; show: boolean };

function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const {
    email,
    accountName,
    can,
    isCompanyOwner,
    isOwner,
    logoDataUri,
    brandTheme,
    accountCount,
  } = useCapabilities();

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
    }
  }, [router]);

  const navItems: NavItem[] = [
    { href: "/dashboard", label: "Dashboard", icon: "dashboard", show: true },
    { href: "/dashboard/catalog", label: "Catalog", icon: "api", show: true },
    { href: "/dashboard/keys", label: "My Keys", icon: "vpn_key", show: can(CAP.API_KEYS) },
    {
      href: "/dashboard/metrics",
      label: "Logs & Métricas",
      icon: "analytics",
      show: can(CAP.LOGS) || can(CAP.CLIENT_USAGE),
    },
    { href: "/dashboard/proxies", label: "Proxies", icon: "lan", show: can(CAP.PROXIES) },
    { href: "/dashboard/users", label: "Usuários", icon: "group", show: isCompanyOwner },
  ];

  return (
    <div className="flex min-h-screen bg-surface text-on-surface font-body">
      <BrandThemeStyle theme={brandTheme} />
      {/* Sidebar */}
      <nav className="fixed left-0 top-0 h-screen w-64 bg-surface-container-low flex flex-col py-8 px-4 z-50">
        <div className="mb-10 px-4">
          {logoDataUri ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logoDataUri}
              alt="Logo da empresa"
              className="max-h-12 max-w-full object-contain"
            />
          ) : (
            <h1 className="text-xl font-black tracking-tight text-on-surface font-headline">
              Bridge API
            </h1>
          )}
          <p className="text-sm text-on-surface-variant mt-1">BridgeAPI by GSV Tech</p>
        </div>

        <ul className="flex-1 space-y-2">
          {navItems.filter((item) => item.show).map((item) => {
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
            <ThemeDropdown
              passwordHref="/dashboard/settings"
              brandingHref={isOwner ? "/dashboard/branding" : undefined}
            />
            <UserMenu
              email={email}
              accountName={accountName}
              canSwitchAccount={accountCount > 1}
            />
          </div>
        </header>

        <main className="mt-16 flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <CapabilitiesProvider>
      <DashboardShell>{children}</DashboardShell>
    </CapabilitiesProvider>
  );
}
