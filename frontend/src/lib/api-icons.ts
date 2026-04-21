const ICONS = ["payments", "person_search", "insights", "cloud_sync", "dataset", "monitoring", "badge", "mail"];

export function apiIcon(api_id: string): string {
  let hash = 0;
  for (let i = 0; i < api_id.length; i++) {
    hash = ((hash << 5) - hash) + api_id.charCodeAt(i);
    hash |= 0;
  }
  return ICONS[Math.abs(hash) % ICONS.length];
}
