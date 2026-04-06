import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import PermissionsManager from "../../src/components/PermissionsManager";

describe("PermissionsManager", () => {
  it("renders grant permission form", async () => {
    render(<PermissionsManager />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /conceder|grant/i })
      ).toBeInTheDocument();
    });
  });

  it("loads clients and APIs into select fields", async () => {
    render(<PermissionsManager />);
    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
      expect(screen.getByText("Stripe")).toBeInTheDocument();
    });
  });

  it("calls POST /permissions when grant button clicked", async () => {
    let grantCalled = false;
    server.use(
      http.post("http://localhost:8000/permissions", () => {
        grantCalled = true;
        return HttpResponse.json({}, { status: 201 });
      })
    );
    render(<PermissionsManager />);
    await waitFor(() =>
      screen.getByRole("button", { name: /conceder|grant/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /conceder|grant/i }));
    await waitFor(() => {
      expect(grantCalled).toBe(true);
    });
  });

  it("shows success feedback after granting permission", async () => {
    render(<PermissionsManager />);
    await waitFor(() =>
      screen.getByRole("button", { name: /conceder|grant/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /conceder|grant/i }));
    await waitFor(() => {
      expect(screen.getByText(/sucesso|success|granted/i)).toBeInTheDocument();
    });
  });

  it("shows error when granting fails (duplicate)", async () => {
    server.use(
      http.post("http://localhost:8000/permissions", () =>
        HttpResponse.json({ detail: "Permission already exists" }, { status: 409 })
      )
    );
    render(<PermissionsManager />);
    await waitFor(() =>
      screen.getByRole("button", { name: /conceder|grant/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /conceder|grant/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
