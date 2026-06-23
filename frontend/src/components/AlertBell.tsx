"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { AlertListResponse } from "@/lib/api";

const POLL_MS = 30_000;

type Props = {
  href: string;
  getAlerts: (status?: string, page?: number, perPage?: number) => Promise<AlertListResponse>;
};

/** Sino no header: contador de alertas ativos, atualizado por polling. */
export function AlertBell({ href, getAlerts }: Props) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const data = await getAlerts("active", 1, 1);
        if (alive) setCount(data.active_count);
      } catch {
        /* silencioso — o sino é best-effort */
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [getAlerts]);

  return (
    <Link
      href={href}
      aria-label={`Alertas${count > 0 ? ` (${count} ativos)` : ""}`}
      className="relative p-2 rounded-full hover:bg-surface-container-low transition-colors"
    >
      <span className="material-symbols-outlined text-on-surface-variant text-[20px]">
        notifications
      </span>
      {count > 0 && (
        <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-error text-on-error text-[10px] font-black flex items-center justify-center">
          {count > 9 ? "9+" : count}
        </span>
      )}
    </Link>
  );
}
