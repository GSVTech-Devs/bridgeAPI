import { render, screen } from "@testing-library/react";
import CatalogPage from "../../src/app/dashboard/catalog/page";

jest.mock("@/lib/api", () => ({
  getCatalog: jest.fn(),
}));

const api = jest.requireMock("@/lib/api");

beforeEach(() => {
  api.getCatalog.mockReset();
});

describe("CatalogPage docs button", () => {
  it("shows 'Ver documentação' linking to the docs page when has_docs", async () => {
    api.getCatalog.mockResolvedValue({
      items: [
        { id: "api-1", name: "Doc API", slug: "doc", base_url: "https://x.com", status: "active", has_docs: true },
      ],
      total: 1,
    });

    render(<CatalogPage />);

    const link = await screen.findByRole("link", { name: /ver documentação/i });
    expect(link).toHaveAttribute("href", "/dashboard/docs/api-1");
  });

  it("falls back to the 'Como usar' block when has_docs is false", async () => {
    api.getCatalog.mockResolvedValue({
      items: [
        { id: "api-2", name: "No Doc API", slug: "nodoc", base_url: "https://y.com", status: "active", has_docs: false },
      ],
      total: 1,
    });

    render(<CatalogPage />);

    expect(await screen.findByText(/como usar/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /ver documentação/i })).not.toBeInTheDocument();
  });
});
