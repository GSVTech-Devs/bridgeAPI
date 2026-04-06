import Link from "next/link";

const cards = [
  { title: "Clientes", desc: "Gerencie e aprove clientes", href: "/admin/clients", color: "bg-blue-500", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" },
  { title: "APIs", desc: "Cadastre e gerencie APIs externas", href: "/admin/apis", color: "bg-purple-500", icon: "M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" },
  { title: "Permissões", desc: "Conceda acesso de clientes às APIs", href: "/admin/permissions", color: "bg-green-500", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" },
  { title: "Métricas", desc: "Veja métricas globais de uso", href: "/admin/metrics", color: "bg-orange-500", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
];

export default function AdminPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Painel Admin</h1>
        <p className="text-gray-500 mt-1">Bem-vindo ao Bridge API — gerencie toda a plataforma por aqui.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {cards.map((c) => (
          <Link key={c.href} href={c.href} className="card hover:shadow-md transition-shadow group">
            <div className="flex items-start gap-4">
              <div className={`${c.color} w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0`}>
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={c.icon} />
                </svg>
              </div>
              <div>
                <h2 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">{c.title}</h2>
                <p className="text-sm text-gray-500 mt-0.5">{c.desc}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
