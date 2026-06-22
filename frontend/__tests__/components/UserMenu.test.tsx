import { render, screen, fireEvent } from "@testing-library/react";
import { UserMenu } from "../../src/components/UserMenu";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("@/lib/auth", () => ({
  clearAuth: jest.fn(),
}));

beforeEach(() => {
  mockPush.mockClear();
  jest.requireMock("@/lib/auth").clearAuth.mockClear();
});

function openMenu(email: string) {
  fireEvent.click(screen.getByTitle(email));
}

describe("UserMenu", () => {
  it("shows the account name and email in the dropdown", () => {
    render(<UserMenu email="owner@acme.com" accountName="Acme" />);
    openMenu("owner@acme.com");
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("owner@acme.com")).toBeInTheDocument();
  });

  it("shows 'Trocar empresa' and navigates to /select-company when enabled", () => {
    render(
      <UserMenu email="owner@acme.com" accountName="Acme" canSwitchAccount />
    );
    openMenu("owner@acme.com");
    const btn = screen.getByRole("button", { name: /trocar empresa/i });
    fireEvent.click(btn);
    expect(mockPush).toHaveBeenCalledWith("/select-company");
  });

  it("hides 'Trocar empresa' when the user has a single company", () => {
    render(
      <UserMenu email="owner@acme.com" accountName="Acme" canSwitchAccount={false} />
    );
    openMenu("owner@acme.com");
    expect(
      screen.queryByRole("button", { name: /trocar empresa/i })
    ).not.toBeInTheDocument();
  });

  it("logs out: clears auth and redirects to the logout href", () => {
    const { clearAuth } = jest.requireMock("@/lib/auth");
    render(
      <UserMenu email="owner@acme.com" accountName="Acme" logoutHref="/login" />
    );
    openMenu("owner@acme.com");
    fireEvent.click(screen.getByRole("button", { name: /sair/i }));
    expect(clearAuth).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith("/login");
  });
});
