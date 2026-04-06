import ClientsList from "@/components/ClientsList";
import ApisList from "@/components/ApisList";
import PermissionsManager from "@/components/PermissionsManager";

export default function AdminPage() {
  return (
    <main>
      <h1>Painel Admin</h1>
      <section>
        <h2>Clientes</h2>
        <ClientsList />
      </section>
      <section>
        <h2>APIs</h2>
        <ApisList />
      </section>
      <section>
        <h2>Permissões</h2>
        <PermissionsManager />
      </section>
    </main>
  );
}
