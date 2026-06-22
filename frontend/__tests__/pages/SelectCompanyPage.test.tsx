import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SelectCompanyPage from "../../src/app/select-company/page";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("@/lib/api", () => ({
  getPortalCompanies: jest.fn(),
  selectCompany: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn().mockReturnValue("identity-token"),
  clearAuth: jest.fn(),
  saveAuthFromToken: jest.fn(),
}));

const api = jest.requireMock("@/lib/api");
const auth = jest.requireMock("@/lib/auth");

beforeEach(() => {
  mockPush.mockClear();
  api.getPortalCompanies.mockReset();
  api.selectCompany.mockReset();
  auth.getToken.mockReset().mockReturnValue("identity-token");
  auth.clearAuth.mockClear();
  auth.saveAuthFromToken.mockClear();
});

describe("SelectCompanyPage", () => {
  it("redirects to /login when there is no token", () => {
    auth.getToken.mockReturnValue(null);
    render(<SelectCompanyPage />);
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("lists the accessible companies", async () => {
    api.getPortalCompanies.mockResolvedValue({
      companies: [
        { account_id: "c1", name: "Acme", type: "company", role: "owner" },
        { account_id: "c2", name: "Beta", type: "individual", role: "member" },
      ],
    });
    render(<SelectCompanyPage />);
    expect(await screen.findByRole("button", { name: /acme/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /beta/i })).toBeInTheDocument();
  });

  it("selects a company: scopes the token and goes to /dashboard", async () => {
    api.getPortalCompanies.mockResolvedValue({
      companies: [{ account_id: "c2", name: "Beta", type: "company", role: "owner" }],
    });
    api.selectCompany.mockResolvedValue({ access_token: "scoped-token" });
    render(<SelectCompanyPage />);
    fireEvent.click(await screen.findByRole("button", { name: /beta/i }));
    await waitFor(() => {
      expect(api.selectCompany).toHaveBeenCalledWith("c2");
      expect(auth.saveAuthFromToken).toHaveBeenCalledWith("scoped-token");
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows an empty-state message when there are no active companies", async () => {
    api.getPortalCompanies.mockResolvedValue({ companies: [] });
    render(<SelectCompanyPage />);
    expect(
      await screen.findByText(/nenhuma empresa ativa/i)
    ).toBeInTheDocument();
  });
});
