// Mapeamento único de status de readiness (healthy/degraded/down/unknown) para
// cor e rótulo. Usado no dashboard e no catálogo para manter consistência.
export type StatusTone = { dot: string; pill: string; label: string };

export function statusTone(status: string): StatusTone {
  switch (status) {
    case "healthy":
      return { dot: "bg-emerald-500", pill: "bg-emerald-50 text-emerald-700", label: "Operacional" };
    case "degraded":
      return { dot: "bg-yellow-500", pill: "bg-yellow-50 text-yellow-700", label: "Degradado" };
    case "down":
      return { dot: "bg-red-500", pill: "bg-red-50 text-red-700", label: "Fora do ar" };
    default:
      return { dot: "bg-gray-400", pill: "bg-surface-container text-on-surface-variant", label: "Desconhecido" };
  }
}
