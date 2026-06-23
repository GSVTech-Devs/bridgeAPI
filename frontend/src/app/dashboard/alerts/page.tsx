"use client";

import { AlertsPanel } from "@/components/AlertsPanel";
import { getClientAlerts, ackClientAlert } from "@/lib/api";

export default function DashboardAlertsPage() {
  return (
    <AlertsPanel
      title="Alertas"
      subtitle="Saldo baixo e falhas nos proxies/captcha que você gerencia."
      getAlerts={getClientAlerts}
      ackAlert={ackClientAlert}
    />
  );
}
