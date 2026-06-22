"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getBranding, getMe } from "@/lib/api";
import type { Capability } from "@/lib/capabilities";

interface CapabilitiesContextType {
  loading: boolean;
  email: string;
  role: string;
  accountType: string | null;
  accountName: string | null;
  isOwner: boolean;
  isCompanyOwner: boolean;
  capabilities: string[];
  logoDataUri: string | null;
  accountCount: number;
  can: (feature: Capability | string) => boolean;
  refresh: () => Promise<void>;
}

const CapabilitiesContext = createContext<CapabilitiesContextType>({
  loading: true,
  email: "",
  role: "",
  accountType: null,
  accountName: null,
  isOwner: false,
  isCompanyOwner: false,
  capabilities: [],
  logoDataUri: null,
  accountCount: 0,
  can: () => false,
  refresh: async () => {},
});

export function CapabilitiesProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [accountType, setAccountType] = useState<string | null>(null);
  const [accountName, setAccountName] = useState<string | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [logoDataUri, setLogoDataUri] = useState<string | null>(null);
  const [accountCount, setAccountCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [me, branding] = await Promise.all([
        getMe(),
        getBranding().catch(() => ({ logo_data_uri: null })),
      ]);
      setEmail(me.email);
      setRole(me.role);
      setAccountType(me.account_type ?? null);
      setAccountName(me.account_name ?? null);
      setIsOwner(Boolean(me.is_owner));
      setCapabilities(me.capabilities ?? []);
      setAccountCount(me.account_count ?? 0);
      setLogoDataUri(branding.logo_data_uri ?? null);
    } catch {
      // erros de auth são tratados pelo apiFetch (redireciona no 401)
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const can = useCallback(
    (feature: Capability | string) => capabilities.includes(feature),
    [capabilities]
  );

  const isCompanyOwner = isOwner && accountType === "company";

  return (
    <CapabilitiesContext.Provider
      value={{
        loading,
        email,
        role,
        accountType,
        accountName,
        isOwner,
        isCompanyOwner,
        capabilities,
        logoDataUri,
        accountCount,
        can,
        refresh,
      }}
    >
      {children}
    </CapabilitiesContext.Provider>
  );
}

export const useCapabilities = () => useContext(CapabilitiesContext);
