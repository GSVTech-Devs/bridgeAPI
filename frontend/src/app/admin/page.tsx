import Link from "next/link";

const actionCards = [
  {
    href: "/admin/clients",
    icon: "group",
    title: "Manage Clientes",
    desc: "View and edit partner access",
    gradient: true,
  },
  {
    href: "/admin/apis",
    icon: "api",
    title: "Explore APIs",
    desc: "Configure bridge endpoints",
    gradient: false,
  },
  {
    href: "/admin/permissions",
    icon: "vpn_key",
    title: "Permissions",
    desc: "Security & authentication",
    gradient: false,
  },
  {
    href: "/admin/metrics",
    icon: "analytics",
    title: "Analytics",
    desc: "Deep usage insights",
    gradient: false,
  },
];

const recentActivity = [
  { icon: "key", title: "New API Key generated for", highlight: "Starlight Corp", time: "2 minutes ago", tag: "Security Audit", id: "982-XQ", isError: false },
  { icon: "dns", title: "Endpoint", highlight: "/v2/auth", time: "14 minutes ago", tag: "Deployment", id: "774-TR", isError: false },
  { icon: "report", title: "Rate limit exceeded for", highlight: "Acme AI", time: "45 minutes ago", tag: "Traffic Incident", id: "112-BB", isError: true },
  { icon: "person_add", title: "New team member", highlight: "Elena Rodriguez", time: "2 hours ago", tag: "Team Management", id: "004-KM", isError: false },
];

export default function AdminPage() {
  return (
    <div>
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold font-headline tracking-tight text-on-surface mb-2">
          Welcome back, Architect.
        </h1>
        <p className="text-on-surface-variant max-w-2xl">
          Monitor your bridge performance and system health across all integrated endpoints in real-time.
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
        {[
          { label: "Total Clients", value: "1,284", delta: "+12%" },
          { label: "API Calls Today", value: "42.8M", delta: "+5.4%" },
          { label: "Success Rate", value: "99.98%", dot: true },
          { label: "Active APIs", value: "24", tag: "Live" },
        ].map((card, i) => (
          <div
            key={i}
            className={`bg-surface-container-lowest p-6 rounded-xl relative overflow-hidden group ${i === 2 ? "border-b-4 border-primary" : ""}`}
          >
            <div className="absolute -right-4 -top-4 w-24 h-24 bg-primary/5 rounded-full group-hover:scale-150 transition-transform duration-500" />
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">{card.label}</p>
            <div className="flex items-end gap-3">
              <span className="text-4xl font-black font-headline text-on-surface">{card.value}</span>
              {card.delta && <span className="text-secondary font-bold text-sm mb-1">{card.delta}</span>}
              {card.dot && <div className="w-2 h-2 rounded-full bg-secondary mb-3 shadow-[0_0_8px_rgba(0,95,175,0.5)]" />}
              {card.tag && <span className="text-slate-400 font-bold text-sm mb-1">{card.tag}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* Action grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        {actionCards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className={`p-8 rounded-xl text-left flex flex-col justify-between h-48 transition-all ${
              card.gradient
                ? "bg-gradient-to-br from-primary to-primary-container text-white hover:shadow-xl hover:shadow-primary/20"
                : "bg-surface-container-low text-on-surface hover:bg-surface-container-high"
            }`}
          >
            <span className={`material-symbols-outlined text-4xl ${card.gradient ? "" : "text-primary"}`}>
              {card.icon}
            </span>
            <div>
              <h3 className={`text-xl font-bold font-headline mb-1 ${card.gradient ? "" : "text-primary"}`}>
                {card.title}
              </h3>
              <p className={`text-sm ${card.gradient ? "text-white/70" : "text-on-surface-variant"}`}>
                {card.desc}
              </p>
            </div>
          </Link>
        ))}
      </div>

      {/* Recent activity */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold font-headline">Recent Activity</h3>
          <button className="text-sm font-bold text-primary flex items-center gap-1">
            View All <span className="material-symbols-outlined text-sm">arrow_forward</span>
          </button>
        </div>
        <div className="space-y-1">
          {recentActivity.map((item) => (
            <div key={item.id} className="flex items-center gap-4 p-4 hover:bg-surface-container-low transition-colors rounded-xl">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${item.isError ? "bg-error-container" : "bg-surface-container-high"}`}>
                <span className={`material-symbols-outlined text-xl ${item.isError ? "text-error" : "text-primary"}`}>
                  {item.icon}
                </span>
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold">
                  {item.title}{" "}
                  <span className={item.isError ? "text-error" : "text-primary"}>{item.highlight}</span>
                </p>
                <p className="text-xs text-on-surface-variant">{item.time} • {item.tag}</p>
              </div>
              <span className="text-xs font-mono text-on-surface-variant bg-surface px-2 py-1 rounded">
                ID: {item.id}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
