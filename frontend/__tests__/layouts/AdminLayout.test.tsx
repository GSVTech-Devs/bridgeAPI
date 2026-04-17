import { render, screen, fireEvent } from "@testing-library/react";
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
}));

beforeEach(() => {
  mockPush.mockClear();
  const { clearAuth } = jest.requireMock("@/lib/auth");
  (clearAuth as jest.Mock).mockClear();
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
});
