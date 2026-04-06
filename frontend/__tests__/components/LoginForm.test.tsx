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
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    render(<LoginForm />);
    expect(
      screen.getByRole("button", { name: /entrar|login|sign in/i })
    ).toBeInTheDocument();
  });

  it("stores token in localStorage on successful admin login", async () => {
    server.use(
      http.post("http://localhost:8000/login", () =>
        HttpResponse.json({
          access_token: "admin-jwt",
          token_type: "bearer",
        })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@bridge.dev" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar|login|sign in/i }));

    await waitFor(() => {
      expect(localStorage.getItem("bridge_token")).toBe("admin-jwt");
    });
  });

  it("redirects admin to /admin after login", async () => {
    server.use(
      http.post("http://localhost:8000/login", () =>
        HttpResponse.json({ access_token: "admin-jwt", token_type: "bearer" })
      ),
      http.get("http://localhost:8000/me", () =>
        HttpResponse.json({ email: "admin@bridge.dev", role: "admin" })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@bridge.dev" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar|login|sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/admin");
    });
  });

  it("redirects client to /dashboard after login", async () => {
    server.use(
      http.post("http://localhost:8000/login", () =>
        HttpResponse.json({ access_token: "client-jwt", token_type: "bearer" })
      ),
      http.get("http://localhost:8000/me", () =>
        HttpResponse.json({ email: "acme@example.com", role: "client" })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "acme@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar|login|sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows error message on invalid credentials", async () => {
    server.use(
      http.post("http://localhost:8000/login", () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
      )
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "wrong@email.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
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
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "secret" },
    });

    const btn = screen.getByRole("button", { name: /entrar|login|sign in/i });
    fireEvent.click(btn);
    expect(btn).toBeDisabled();
  });
});
