import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import LoginForm from "../../src/components/LoginForm";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

beforeEach(() => {
  localStorage.clear();
  mockPush.mockClear();
});

describe("LoginForm", () => {
  it("renders email and password fields", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/senha/i)).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    render(<LoginForm />);
    expect(
      screen.getByRole("button", { name: /entrar|login|sign in/i })
    ).toBeInTheDocument();
  });

  // e30 = base64url({}) — minimal JWT header; payload encodes {"sub":"1","role":"admin"}
  const ADMIN_JWT = "e30.eyJzdWIiOiIxIiwicm9sZSI6ImFkbWluIn0.";
  // payload encodes {"sub":"2","role":"client"}
  const CLIENT_JWT = "e30.eyJzdWIiOiIyIiwicm9sZSI6ImNsaWVudCJ9.";

  it("stores token in localStorage on successful admin login", async () => {
    server.use(
      http.post("http://localhost:8000/auth/login", () =>
        HttpResponse.json({
          access_token: ADMIN_JWT,
          token_type: "bearer",
        })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@bridge.dev" },
    });
    fireEvent.change(screen.getByLabelText(/senha/i), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar|login|sign in/i }));

    await waitFor(() => {
      expect(localStorage.getItem("bridge_token")).toBe(ADMIN_JWT);
    });
  });

  it("redirects admin to /admin after login", async () => {
    server.use(
      http.post("http://localhost:8000/auth/login", () =>
        HttpResponse.json({ access_token: ADMIN_JWT, token_type: "bearer" })
      ),
      http.get("http://localhost:8000/me", () =>
        HttpResponse.json({ email: "admin@bridge.dev", role: "admin" })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@bridge.dev" },
    });
    fireEvent.change(screen.getByLabelText(/senha/i), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar|login|sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/admin");
    });
  });

  it("redirects client to /dashboard after login", async () => {
    server.use(
      http.post("http://localhost:8000/auth/login", () =>
        HttpResponse.json({ access_token: CLIENT_JWT, token_type: "bearer" })
      ),
      http.get("http://localhost:8000/me", () =>
        HttpResponse.json({ email: "acme@example.com", role: "client" })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "acme@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/senha/i), {
      target: { value: "pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar|login|sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows error message on invalid credentials", async () => {
    server.use(
      http.post("http://localhost:8000/auth/login", () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
      ),
      http.post("http://localhost:8000/clients/login", () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "wrong@email.com" },
    });
    fireEvent.change(screen.getByLabelText(/senha/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar|login|sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("disables submit button while loading", async () => {
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@bridge.dev" },
    });
    fireEvent.change(screen.getByLabelText(/senha/i), {
      target: { value: "secret" },
    });

    const btn = screen.getByRole("button", { name: /entrar|login|sign in/i });
    fireEvent.click(btn);
    expect(btn).toBeDisabled();
  });
});
