import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import ApiCatalog from "../../src/components/ApiCatalog";

describe("ApiCatalog", () => {
  it("shows loading state initially", () => {
    render(<ApiCatalog />);
    expect(screen.getByText(/carregando|loading/i)).toBeInTheDocument();
  });

  it("renders authorized APIs after loading", async () => {
    render(<ApiCatalog />);
    await waitFor(() => {
      expect(screen.getByText("Stripe")).toBeInTheDocument();
    });
  });

  it("shows Bridge URL when API has a slug", async () => {
    render(<ApiCatalog />);
    await waitFor(() => {
      expect(screen.getByTestId("bridge-url")).toBeInTheDocument();
    });
    expect(screen.getByTestId("bridge-url").textContent).toContain("/apis/stripe/");
  });

  it("shows base_url when API has no slug", async () => {
    server.use(
      http.get("http://localhost:8000/catalog", () =>
        HttpResponse.json({
          items: [{ id: "a2", name: "Raw API", base_url: "https://raw.example.com", status: "active" }],
          total: 1,
        })
      )
    );
    render(<ApiCatalog />);
    await waitFor(() => {
      expect(screen.getByText(/raw\.example\.com/i)).toBeInTheDocument();
    });
    expect(screen.queryByTestId("bridge-url")).not.toBeInTheDocument();
  });

  it("shows status badge for each API", async () => {
    render(<ApiCatalog />);
    await waitFor(() => {
      expect(screen.getByText(/active/i)).toBeInTheDocument();
    });
  });

  it("shows empty state when no APIs authorized", async () => {
    server.use(
      http.get("http://localhost:8000/catalog", () =>
        HttpResponse.json({ items: [], total: 0 })
      )
    );
    render(<ApiCatalog />);
    await waitFor(() => {
      expect(screen.getByText(/nenhuma|no api|sem api/i)).toBeInTheDocument();
    });
  });

  it("shows error when catalog fails to load", async () => {
    server.use(
      http.get("http://localhost:8000/catalog", () =>
        HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })
      )
    );
    render(<ApiCatalog />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
