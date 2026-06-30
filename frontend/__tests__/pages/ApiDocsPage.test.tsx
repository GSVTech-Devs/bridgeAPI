import { render, screen } from "@testing-library/react";
import ApiDocsPage from "../../src/app/dashboard/docs/[apiId]/page";

jest.mock("next/navigation", () => ({
  useParams: () => ({ apiId: "api-1" }),
}));

jest.mock("@/lib/api", () => ({
  getUserApiDocs: jest.fn(),
}));

const api = jest.requireMock("@/lib/api");

beforeEach(() => {
  api.getUserApiDocs.mockReset();
});

describe("ApiDocsPage", () => {
  it("renders the API title and an operation with the bridge URL (path substituted)", async () => {
    api.getUserApiDocs.mockResolvedValue({
      api_id: "api-1",
      api_name: "Solver API",
      slug: "solver",
      base_url: "https://api.solver.com",
      operations: [
        {
          method: "GET",
          path: "/v1/people",
          summary: "List people",
          description: null,
          parameters: [
            { name: "cpf", in: "query", required: true, description: "CPF", type: "string" },
          ],
          request_example: null,
          responses: [{ status: "200", description: "OK", example: null }],
        },
      ],
    });

    render(<ApiDocsPage />);

    expect(await screen.findByText("Solver API")).toBeInTheDocument();
    expect(screen.getByText("/v1/people")).toBeInTheDocument();
    // URL no formato bridge com o path concreto no lugar de {query}
    expect(
      screen.getByText(/\/apis\/solver\/v1\/people\/\{seu-token\}/)
    ).toBeInTheDocument();
    expect(screen.getByText("cpf")).toBeInTheDocument();
  });

  it("shows an empty-state when there are no visible operations", async () => {
    api.getUserApiDocs.mockResolvedValue({
      api_id: "api-1",
      api_name: "Empty API",
      slug: "empty",
      base_url: "https://api.empty.com",
      operations: [],
    });

    render(<ApiDocsPage />);

    expect(
      await screen.findByText(/documentação ainda não disponível/i)
    ).toBeInTheDocument();
  });
});
