import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import ClientsList from "../../src/components/ClientsList";

describe("ClientsList", () => {
  it("shows loading state initially", () => {
    render(<ClientsList />);
    expect(screen.getByText(/carregando|loading/i)).toBeInTheDocument();
  });

  it("renders list of clients after loading", async () => {
    render(<ClientsList />);
    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
      expect(screen.getByText("Beta Ltd")).toBeInTheDocument();
    });
  });

  it("shows client status badges", async () => {
    render(<ClientsList />);
    await waitFor(() => {
      expect(screen.getByText(/active/i)).toBeInTheDocument();
      expect(screen.getByText(/pending/i)).toBeInTheDocument();
    });
  });

  it("shows approve button for pending clients", async () => {
    render(<ClientsList />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /aprovar|approve/i })
      ).toBeInTheDocument();
    });
  });

  it("calls approve endpoint when approve button clicked", async () => {
    let approvedId = "";
    server.use(
      http.patch("http://localhost:8000/clients/:id/approve", ({ params }) => {
        approvedId = params.id as string;
        return HttpResponse.json({ id: params.id, status: "active" });
      })
    );
    render(<ClientsList />);
    await waitFor(() =>
      screen.getByRole("button", { name: /aprovar|approve/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /aprovar|approve/i }));
    await waitFor(() => {
      expect(approvedId).toBe("c2");
    });
  });

  it("shows reject button for pending clients", async () => {
    render(<ClientsList />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /rejeitar|reject/i })
      ).toBeInTheDocument();
    });
  });

  it("shows error message when API fails", async () => {
    server.use(
      http.get("http://localhost:8000/clients", () =>
        HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })
      )
    );
    render(<ClientsList />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
