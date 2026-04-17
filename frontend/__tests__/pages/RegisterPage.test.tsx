import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import RegisterPage from "../../src/app/clients/register/page";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

beforeEach(() => {
  mockPush.mockClear();
});

describe("RegisterPage", () => {
  it("renders all form fields", () => {
    render(<RegisterPage />);
    expect(screen.getByLabelText(/nome completo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/e-mail/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^senha$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirme/i)).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    render(<RegisterPage />);
    expect(
      screen.getByRole("button", { name: /criar conta/i })
    ).toBeInTheDocument();
  });

  it("shows error when passwords do not match (client-side, no API call)", async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/nome completo/i), {
      target: { value: "Acme Corp" },
    });
    fireEvent.change(screen.getByLabelText(/e-mail/i), {
      target: { value: "acme@corp.com" },
    });
    fireEvent.change(screen.getByLabelText(/^senha$/i), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText(/confirme/i), {
      target: { value: "differentpass" },
    });
    fireEvent.click(screen.getByRole("button", { name: /criar conta/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent(/senhas não coincidem/i);
    });
  });

  it("does not call API when passwords do not match", async () => {
    let apiCalled = false;
    server.use(
      http.post("http://localhost:8000/clients/register", () => {
        apiCalled = true;
        return HttpResponse.json({}, { status: 201 });
      })
    );
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/^senha$/i), {
      target: { value: "abc12345" },
    });
    fireEvent.change(screen.getByLabelText(/confirme/i), {
      target: { value: "xyz99999" },
    });
    fireEvent.click(screen.getByRole("button", { name: /criar conta/i }));

    // Aguarda um tick para garantir que nenhuma requisição assíncrona foi disparada
    await new Promise((r) => setTimeout(r, 50));
    expect(apiCalled).toBe(false);
  });

  it("shows success state after successful registration", async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/nome completo/i), {
      target: { value: "Acme Corp" },
    });
    fireEvent.change(screen.getByLabelText(/e-mail/i), {
      target: { value: "acme@corp.com" },
    });
    fireEvent.change(screen.getByLabelText(/^senha$/i), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText(/confirme/i), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /criar conta/i }));

    await waitFor(() => {
      expect(screen.getByText(/cadastro realizado/i)).toBeInTheDocument();
    });
  });

  it("shows pending approval message in success state", async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/nome completo/i), {
      target: { value: "Beta Ltd" },
    });
    fireEvent.change(screen.getByLabelText(/e-mail/i), {
      target: { value: "beta@ltd.com" },
    });
    fireEvent.change(screen.getByLabelText(/^senha$/i), {
      target: { value: "mypassword" },
    });
    fireEvent.change(screen.getByLabelText(/confirme/i), {
      target: { value: "mypassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: /criar conta/i }));

    await waitFor(() => {
      expect(screen.getByText(/pendente de aprovação/i)).toBeInTheDocument();
    });
  });

  it("shows go-to-login button in success state and navigates on click", async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/nome completo/i), {
      target: { value: "Gamma SA" },
    });
    fireEvent.change(screen.getByLabelText(/e-mail/i), {
      target: { value: "gamma@sa.com" },
    });
    fireEvent.change(screen.getByLabelText(/^senha$/i), {
      target: { value: "pass12345" },
    });
    fireEvent.change(screen.getByLabelText(/confirme/i), {
      target: { value: "pass12345" },
    });
    fireEvent.click(screen.getByRole("button", { name: /criar conta/i }));

    await waitFor(() =>
      screen.getByRole("button", { name: /ir para o login/i })
    );
    fireEvent.click(screen.getByRole("button", { name: /ir para o login/i }));

    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("shows error when email is already registered (409)", async () => {
    server.use(
      http.post("http://localhost:8000/clients/register", () =>
        HttpResponse.json(
          { detail: "Email already registered" },
          { status: 409 }
        )
      )
    );
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/nome completo/i), {
      target: { value: "Dup Corp" },
    });
    fireEvent.change(screen.getByLabelText(/e-mail/i), {
      target: { value: "dup@corp.com" },
    });
    fireEvent.change(screen.getByLabelText(/^senha$/i), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText(/confirme/i), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /criar conta/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent(
        /email already registered/i
      );
    });
  });

  it("disables button while loading", async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/nome completo/i), {
      target: { value: "Loading Corp" },
    });
    fireEvent.change(screen.getByLabelText(/e-mail/i), {
      target: { value: "loading@corp.com" },
    });
    fireEvent.change(screen.getByLabelText(/^senha$/i), {
      target: { value: "pass1234" },
    });
    fireEvent.change(screen.getByLabelText(/confirme/i), {
      target: { value: "pass1234" },
    });

    const btn = screen.getByRole("button", { name: /criar conta/i });
    fireEvent.click(btn);
    expect(btn).toBeDisabled();
  });
});
