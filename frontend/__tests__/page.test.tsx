import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("Home page", () => {
  it("renders the Bridge API heading", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: /bridge api/i })).toBeInTheDocument();
  });

  it("renders the platform description", () => {
    render(<Home />);
    expect(screen.getByText(/centralized api gateway/i)).toBeInTheDocument();
  });
});
