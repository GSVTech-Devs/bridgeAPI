import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import ApiDocsPanel from "../../src/components/ApiDocsPanel";

const BASE = "http://localhost:8000";
const API_ID = "api-1";

function docOp(id: string, path: string) {
  return {
    id,
    method: "GET",
    path,
    summary: "op",
    description: null,
    visible: true,
    parameters: [],
    request_example: null,
    responses: [],
  };
}

describe("ApiDocsPanel — limpar documentação importada", () => {
  it("desabilita o botao limpar quando nao ha operacoes", async () => {
    server.use(
      http.get(`${BASE}/apis/${API_ID}/docs`, () =>
        HttpResponse.json({ items: [], total: 0 })
      )
    );
    render(<ApiDocsPanel apiId={API_ID} hasOpenApi={false} />);

    const btn = await screen.findByRole("button", { name: /limpar documentação/i });
    expect(btn).toBeDisabled();
  });

  it("remove as operacoes apos confirmar e mostra a contagem", async () => {
    let deleteCalled = false;
    server.use(
      http.get(`${BASE}/apis/${API_ID}/docs`, () =>
        HttpResponse.json({
          items: deleteCalled ? [] : [docOp("o1", "/a"), docOp("o2", "/b")],
          total: deleteCalled ? 0 : 2,
        })
      ),
      http.delete(`${BASE}/apis/${API_ID}/docs`, () => {
        deleteCalled = true;
        return HttpResponse.json({ removed: 2 });
      })
    );

    render(<ApiDocsPanel apiId={API_ID} hasOpenApi={true} />);

    // operações carregadas
    await screen.findByText("/a");

    const clearBtn = screen.getByRole("button", { name: /limpar documentação/i });
    expect(clearBtn).toBeEnabled();
    fireEvent.click(clearBtn);

    // confirmação inline
    const confirmBtn = await screen.findByRole("button", { name: /confirmar/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => expect(deleteCalled).toBe(true));
    await waitFor(() =>
      expect(screen.getByText(/documentação importada removida: 2/i)).toBeInTheDocument()
    );
    // a lista recarrega vazia
    await waitFor(() => expect(screen.queryByText("/a")).not.toBeInTheDocument());
  });

  it("cancelar fecha a confirmacao sem chamar o delete", async () => {
    let deleteCalled = false;
    server.use(
      http.get(`${BASE}/apis/${API_ID}/docs`, () =>
        HttpResponse.json({ items: [docOp("o1", "/a")], total: 1 })
      ),
      http.delete(`${BASE}/apis/${API_ID}/docs`, () => {
        deleteCalled = true;
        return HttpResponse.json({ removed: 1 });
      })
    );

    render(<ApiDocsPanel apiId={API_ID} hasOpenApi={true} />);
    await screen.findByText("/a");

    fireEvent.click(screen.getByRole("button", { name: /limpar documentação/i }));
    fireEvent.click(await screen.findByRole("button", { name: /cancelar/i }));

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /confirmar/i })).not.toBeInTheDocument()
    );
    expect(deleteCalled).toBe(false);
  });
});
