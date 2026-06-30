import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";

// react-markdown é ESM puro e não é transformado pelo jest; o componente Markdown
// só aparece no preview de docs (fora do escopo deste teste), então mockamos.
jest.mock("@/components/Markdown", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => children ?? null,
}));

import ApisPage from "../../src/app/admin/apis/page";

/**
 * Comportamento de auth no cadastro de API:
 * para o método POST a credencial deve ir no header Authorization: Bearer
 * (auth_type=bearer), não embutida na URL via {token}.
 */
describe("AdminApisPage — auth por método", () => {
  async function openForm() {
    render(<ApisPage />);
    const openBtn = await screen.findByRole("button", { name: /register new api/i });
    fireEvent.click(openBtn);
    // aguarda o form abrir
    return await screen.findByDisplayValue("Repassar o método do cliente");
  }

  it("seleciona POST e o Auth Type vira Bearer Token por padrão", async () => {
    const methodSelect = (await openForm()) as HTMLSelectElement;
    const authSelect = screen.getByDisplayValue("API Key") as HTMLSelectElement;

    expect(authSelect.value).toBe("api_key");

    fireEvent.change(methodSelect, { target: { value: "POST" } });

    expect(authSelect.value).toBe("bearer");
  });

  it("nao mexe no Auth Type quando o metodo nao e POST", async () => {
    const methodSelect = (await openForm()) as HTMLSelectElement;
    const authSelect = screen.getByDisplayValue("API Key") as HTMLSelectElement;

    fireEvent.change(methodSelect, { target: { value: "GET" } });

    expect(authSelect.value).toBe("api_key");
  });

  it("bloqueia o submit quando Bearer Token tem {token} na URL Template", async () => {
    let createCalled = false;
    server.use(
      http.post("http://localhost:8000/apis", async () => {
        createCalled = true;
        return HttpResponse.json({ id: "new", name: "Acme", auth_type: "bearer" });
      })
    );

    await openForm();

    fireEvent.change(screen.getByPlaceholderText("e.g. Real-Time Finance Connector"), {
      target: { value: "Acme" },
    });
    fireEvent.change(screen.getByPlaceholderText("https://api.provider.com/v1"), {
      target: { value: "https://api.acme.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••••••••••"), {
      target: { value: "secret-token" },
    });
    fireEvent.change(screen.getByDisplayValue("API Key"), {
      target: { value: "bearer" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("https://api.example.com/v1/{query}/{token}"),
      { target: { value: "https://api.acme.com/{query}/{token}" } }
    );

    fireEvent.click(screen.getByRole("button", { name: /deploy api bridge/i }));

    // a validação impede a chamada de criação (config incoerente)
    await waitFor(() => {
      expect(
        screen.getAllByText(/remova.*da url template/i).length
      ).toBeGreaterThan(0);
    });
    expect(createCalled).toBe(false);
  });
});
