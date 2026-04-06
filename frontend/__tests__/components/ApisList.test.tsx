import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import ApisList from "../../src/components/ApisList";

describe("ApisList", () => {
  it("shows loading state initially", () => {
    render(<ApisList />);
    expect(screen.getByText(/carregando|loading/i)).toBeInTheDocument();
  });

  it("renders list of APIs after loading", async () => {
    render(<ApisList />);
    await waitFor(() => {
      expect(screen.getByText("Stripe")).toBeInTheDocument();
      expect(screen.getByText("SendGrid")).toBeInTheDocument();
    });
  });

  it("shows status for each API", async () => {
    render(<ApisList />);
    await waitFor(() => {
      expect(screen.getByText("active")).toBeInTheDocument();
      expect(screen.getByText("inactive")).toBeInTheDocument();
    });
  });

  it("shows disable button for active APIs", async () => {
    render(<ApisList />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /desabilitar|disable/i })
      ).toBeInTheDocument();
    });
  });

  it("calls disable endpoint when button clicked", async () => {
    let disabledId = "";
    server.use(
      http.patch("http://localhost:8000/apis/:id/disable", ({ params }) => {
        disabledId = params.id as string;
        return HttpResponse.json({ id: params.id, status: "inactive" });
      })
    );
    render(<ApisList />);
    await waitFor(() =>
      screen.getByRole("button", { name: /desabilitar|disable/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /desabilitar|disable/i }));
    await waitFor(() => {
      expect(disabledId).toBe("a1");
    });
  });

  it("shows base_url for each API", async () => {
    render(<ApisList />);
    await waitFor(() => {
      expect(screen.getByText(/api\.stripe\.com/i)).toBeInTheDocument();
    });
  });

  it("shows error message when API call fails", async () => {
    server.use(
      http.get("http://localhost:8000/apis", () =>
        HttpResponse.json({ detail: "Forbidden" }, { status: 403 })
      )
    );
    render(<ApisList />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
