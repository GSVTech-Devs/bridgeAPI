"use client";

import { useEffect, useRef, useState } from "react";
import { useTheme, type Theme } from "@/contexts/ThemeContext";

const options: { value: Theme; label: string; icon: string }[] = [
  { value: "light", label: "Claro", icon: "light_mode" },
  { value: "dark", label: "Escuro", icon: "dark_mode" },
  { value: "system", label: "Sistema", icon: "computer" },
];

export function ThemeDropdown() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="p-2 rounded-full hover:bg-surface-container-low transition-colors"
        title="Configurações de tema"
      >
        <span className="material-symbols-outlined text-on-surface-variant text-[20px]">settings</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-48 bg-surface-container-low border border-outline-variant/20 rounded-xl shadow-lg z-50 overflow-hidden py-1">
          <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest px-4 pt-2 pb-1.5">
            Aparência
          </p>
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => {
                setTheme(opt.value);
                setOpen(false);
              }}
              className={`flex items-center gap-3 w-full px-4 py-2 text-sm transition-colors ${
                theme === opt.value
                  ? "text-primary font-semibold bg-primary/10"
                  : "text-on-surface hover:bg-surface-container"
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">{opt.icon}</span>
              <span>{opt.label}</span>
              {theme === opt.value && (
                <span className="material-symbols-outlined text-[16px] ml-auto">check</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
