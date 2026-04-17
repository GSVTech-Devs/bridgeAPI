import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AdminLayout from "../../src/app/admin/layout";

const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/admin",
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

beforeEach(() => {
  mockPush.mockClear();
  const { clearAuth, getToken } = jest.requireMock("@/lib/auth");
  (clearAuth as jest.Mock).mockClear();
  (getToken as jest.Mock).mockReset().mockReturnValue("valid-token");
});

describe("AdminLayout", () => {
  it("renders children content", () => {
    render(
      <AdminLayout>
        <div data-testid="content">page content</div>
      </AdminLayout>
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("renders nav items: Dashboard, Clientes, APIs, Permissões, Métricas", () => {
    render(<AdminLayout><div /></AdminLayout>);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Clientes")).toBeInTheDocument();
    expect(screen.getByText("APIs")).toBeInTheDocument();
    expect(screen.getByText("Permissões")).toBeInTheDocument();
    expect(screen.getByText("Métricas")).toBeInTheDocument();
  });

  it("renders brand header", () => {
    render(<AdminLayout><div /></AdminLayout>);
    expect(screen.getByText("GSV Tech")).toBeInTheDocument();
  });

  it("renders logout button", () => {
    render(<AdminLayout><div /></AdminLayout>);
    expect(screen.getByRole("button", { name: /sair/i })).toBeInTheDocument();
  });

  it("calls clearAuth when logout button is clicked", () => {
    const { clearAuth } = jest.requireMock("@/lib/auth");
    render(<AdminLayout><div /></AdminLayout>);
    fireEvent.click(screen.getByRole("button", { name: /sair/i }));
    expect(clearAuth).toHaveBeenCalledTimes(1);
  });

  it("redirects to /login after logout", () => {
    render(<AdminLayout><div /></AdminLayout>);
    fireEvent.click(screen.getByRole("button", { name: /sair/i }));
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("highlights the active nav item based on pathname", () => {
    render(<AdminLayout><div /></AdminLayout>);
    // pathname = "/admin", so "Dashboard" link should have active styling
    const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
    expect(dashboardLink).toHaveClass("text-primary");
  });

  it("redirects to /login on mount when no token is stored", async () => {
    const { getToken } = jest.requireMock("@/lib/auth");
    (getToken as jest.Mock).mockReturnValue(null);
    render(<AdminLayout><div /></AdminLayout>);
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  it("does not redirect when token is present", () => {
    render(<AdminLayout><div /></AdminLayout>);
    expect(mockPush).not.toHaveBeenCalledWith("/login");
  });
});
