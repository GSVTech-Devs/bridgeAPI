import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import ApiKeysList from "../../src/components/ApiKeysList";

describe("ApiKeysList", () => {
  it("shows loading state initially", () => {
    render(<ApiKeysList />);
    expect(screen.getByText(/carregando|loading/i)).toBeInTheDocument();
  });

  it("renders existing keys after loading", async () => {
    render(<ApiKeysList />);
    await waitFor(() => {
      expect(screen.getByText("prod-key")).toBeInTheDocument();
    });
  });

  it("shows key prefix (not full secret)", async () => {
    render(<ApiKeysList />);
    await waitFor(() => {
      expect(screen.getByText(/brg_abc/)).toBeInTheDocument();
    });
  });

  it("shows key status", async () => {
    render(<ApiKeysList />);
    await waitFor(() => {
      expect(screen.getByText(/active/i)).toBeInTheDocument();
    });
  });

  it("shows create key button", async () => {
    render(<ApiKeysList />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /criar|create|nova|new/i })
      ).toBeInTheDocument();
    });
  });

  it("calls POST /keys when create button clicked", async () => {
    let createCalled = false;
    server.use(
      http.post("http://localhost:8000/keys", () => {
        createCalled = true;
        return HttpResponse.json(
          {
            id: "k2",
            name: "new-key",
            key_prefix: "brg_xyz",
            api_key: "brg_xyz_full-secret",
            status: "active",
            created_at: "2024-06-01T00:00:00Z",
          },
          { status: 201 }
        );
      })
    );
    render(<ApiKeysList />);
    await waitFor(() =>
      screen.getByRole("button", { name: /criar|create|nova|new/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /criar|create|nova|new/i }));
    await waitFor(() => {
      expect(createCalled).toBe(true);
    });
  });

  it("shows full secret once after key creation", async () => {
    render(<ApiKeysList />);
    await waitFor(() =>
      screen.getByRole("button", { name: /criar|create|nova|new/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /criar|create|nova|new/i }));
    await waitFor(() => {
      expect(screen.getByText(/brg_xyz_full-secret/)).toBeInTheDocument();
    });
  });

  it("shows revoke button for active keys", async () => {
    render(<ApiKeysList />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /revogar|revoke/i })
      ).toBeInTheDocument();
    });
  });

  it("calls PATCH /keys/:id/revoke when revoke clicked", async () => {
    let revokedId = "";
    server.use(
      http.patch("http://localhost:8000/keys/:id/revoke", ({ params }) => {
        revokedId = params.id as string;
        return HttpResponse.json({ id: params.id, status: "revoked" });
      })
    );
    render(<ApiKeysList />);
    await waitFor(() =>
      screen.getByRole("button", { name: /revogar|revoke/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /revogar|revoke/i }));
    await waitFor(() => {
      expect(revokedId).toBe("k1");
    });
  });
});
