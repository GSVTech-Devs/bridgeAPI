import { render, screen, fireEvent } from "@testing-library/react";
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
}));

beforeEach(() => {
  mockPush.mockClear();
  const { clearAuth } = jest.requireMock("@/lib/auth");
  (clearAuth as jest.Mock).mockClear();
});

describe("DashboardLayout", () => {
  it("renders children content", () => {
    render(
      <DashboardLayout>
        <div data-testid="page">dashboard page</div>
      </DashboardLayout>
    );
    expect(screen.getByTestId("page")).toBeInTheDocument();
  });

  it("renders nav items: Dashboard, Catalog, My Keys", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    expect(screen.getByRole("link", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /catalog/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /my keys/i })).toBeInTheDocument();
  });

  it("renders 'Bridge API' brand in sidebar", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    expect(screen.getAllByText(/bridge api/i).length).toBeGreaterThan(0);
  });

  it("renders logout button", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
    expect(screen.getByRole("button", { name: /sair/i })).toBeInTheDocument();
  });

  it("calls clearAuth when logout is clicked", () => {
    const { clearAuth } = jest.requireMock("@/lib/auth");
    render(<DashboardLayout><div /></DashboardLayout>);
    fireEvent.click(screen.getByRole("button", { name: /sair/i }));
    expect(clearAuth).toHaveBeenCalledTimes(1);
  });

  it("redirects to /login after logout", () => {
    render(<DashboardLayout><div /></DashboardLayout>);
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
});
