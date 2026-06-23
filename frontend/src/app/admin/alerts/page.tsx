"use client";

import { AlertsPanel } from "@/components/AlertsPanel";
import { getAdminAlerts, ackAdminAlert } from "@/lib/api";

export default function AdminAlertsPage() {
  return (
    <AlertsPanel
      title="Alertas"
      subtitle="APIs fora do ar/degradadas, captcha sem saldo e proxies falhando."
      getAlerts={getAdminAlerts}
      ackAlert={ackAdminAlert}
    />
  );
}
