import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DashboardLayout from "../../src/app/dashboard/layout";

const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/dashboard",
}));

jest.mock("next/link", () => {
  const Link = ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  );
  Link.displayName = "Link";
  return Link;
});

jest.mock("@/lib/auth", () => ({
  clearAuth: jest.fn(),
  getToken: jest.fn().mockReturnValue("valid-token"),
}));

// O CapabilitiesContext busca /auth/me e /portal/branding ao montar; mockamos
// para tornar a navbar (gated por capabilities) determinística.
jest.mock("@/lib/api", () => ({
  getMe: jest.fn().mockResolvedValue({
    email: "owner@acme.com",
    role: "owner",
    account_id: "acc-1",
    capabilities: ["catalog", "docs", "api_keys"],
    account_type: "company",
    account_name: "Acme",
    is_owner: true,
    account_count: 1,
  }),
  getBranding: jest.fn().mockResolvedValue({ logo_data_uri: null }),
}));

beforeEach(() => {
  mockPush.mockClear();
  const { clearAuth, getToken } = jest.requireMock("@/lib/auth");
  (clearAuth as jest.Mock).mockClear();
  (getToken as jest.Mock).mockReset().mockReturnValue("valid-token");
});

/** Abre o dropdown do UserMenu (onde fica o botão Sair / Trocar empresa). */
async function openUserMenu() {
  const avatar = await screen.findByTitle("owner@acme.com");
  fireEvent.click(avatar);
}

describe("DashboardLayout", () => {
  it("renders children content", () => {
    render(
      <DashboardLayout>
        <div data-testid="page">dashboard page</div>
      </DashboardLayout>
    );
    expect(screen.getByTestId("page")).toBeInTheDocument();
  });

  it("renders nav items: Dashboard, Catalog, My Keys", async () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    expect(screen.getByRole("link", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /catalog/i })).toBeInTheDocument();
    // "My Keys" é gated por capability api_keys, carregada async do /auth/me
    expect(await screen.findByRole("link", { name: /my keys/i })).toBeInTheDocument();
  });

  it("renders 'Bridge API' brand in sidebar", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    expect(screen.getAllByText(/bridge api/i).length).toBeGreaterThan(0);
  });

  it("renders logout button", async () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    await openUserMenu();
    expect(screen.getByRole("button", { name: /sair/i })).toBeInTheDocument();
  });

  it("calls clearAuth when logout is clicked", async () => {
    const { clearAuth } = jest.requireMock("@/lib/auth");
    render(<DashboardLayout><div /></DashboardLayout>);
    await openUserMenu();
    fireEvent.click(screen.getByRole("button", { name: /sair/i }));
    expect(clearAuth).toHaveBeenCalledTimes(1);
  });

  it("redirects to /login after logout", async () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    await openUserMenu();
    fireEvent.click(screen.getByRole("button", { name: /sair/i }));
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("highlights active nav item: /dashboard link gets active class", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    // pathname = "/dashboard" → Dashboard link should be active
    const links = screen.getAllByRole("link", { name: /dashboard/i });
    const dashLink = links.find((l) => l.getAttribute("href") === "/dashboard");
    expect(dashLink).toHaveClass("text-primary");
  });

  it("renders search input in the top header", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    expect(
      screen.getByPlaceholderText(/search resources/i)
    ).toBeInTheDocument();
  });

  it("redirects to /login on mount when no token is stored", async () => {
    const { getToken } = jest.requireMock("@/lib/auth");
    (getToken as jest.Mock).mockReturnValue(null);
    render(<DashboardLayout><div /></DashboardLayout>);
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  it("does not redirect when token is present", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    expect(mockPush).not.toHaveBeenCalledWith("/login");
  });
});
