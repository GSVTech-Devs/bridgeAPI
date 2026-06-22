"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clearAuth } from "@/lib/auth";

export function UserMenu({
  email,
  accountName,
  logoutHref = "/login",
  canSwitchAccount = false,
  switchAccountHref = "/select-company",
}: {
  email: string;
  accountName?: string | null;
  logoutHref?: string;
  canSwitchAccount?: boolean;
  switchAccountHref?: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const initial = email.trim().charAt(0).toUpperCase() || "?";

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function handleLogout() {
    clearAuth();
    router.push(logoutHref);
  }

  function handleSwitchAccount() {
    setOpen(false);
    router.push(switchAccountHref);
  }

  return (
    <div className="relative ml-1" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        title={email}
        aria-haspopup="menu"
        aria-expanded={open}
        className="h-8 w-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-bold text-sm hover:opacity-90 transition-opacity"
      >
        {initial}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-60 bg-surface-container-low border border-outline-variant/20 rounded-xl shadow-lg z-50 overflow-hidden py-1">
          <div className="px-4 py-3">
            <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-0.5">
              Conta
            </p>
            {accountName && (
              <p
                className="text-sm font-bold text-on-surface truncate"
                title={accountName}
              >
                {accountName}
              </p>
            )}
            <p className="text-xs text-on-surface-variant truncate" title={email}>
              {email}
            </p>
          </div>
          <div className="border-t border-outline-variant/15" />
          {canSwitchAccount && (
            <button
              onClick={handleSwitchAccount}
              className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-on-surface hover:bg-surface-container transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]">swap_horiz</span>
              <span>Trocar empresa</span>
            </button>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-on-surface hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">logout</span>
            <span>Sair</span>
          </button>
        </div>
      )}
    </div>
  );
}
