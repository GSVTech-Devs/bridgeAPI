import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import MetricsDashboard from "../../src/components/MetricsDashboard";

describe("MetricsDashboard", () => {
  it("shows loading state initially", () => {
    render(<MetricsDashboard />);
    expect(screen.getByText(/carregando|loading/i)).toBeInTheDocument();
  });

  it("renders total requests after loading", async () => {
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("1250")).toBeInTheDocument();
    });
  });

  it("renders error rate", async () => {
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId("error-rate")).toHaveTextContent("2.5");
    });
  });

  it("renders average latency", async () => {
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId("avg-latency")).toHaveTextContent("87.3");
    });
  });

  it("renders total cost", async () => {
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId("total-cost")).toHaveTextContent("12.5");
    });
  });

  it("renders billable vs non-billable requests", async () => {
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("1100")).toBeInTheDocument();
      expect(screen.getByText("150")).toBeInTheDocument();
    });
  });

  it("shows error when metrics API fails", async () => {
    server.use(
      http.get("http://localhost:8000/metrics/dashboard", () =>
        HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })
      )
    );
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("shows all metric section headings", async () => {
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(
        screen.getByText(/total.*request|requisições/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/latência|latency/i)).toBeInTheDocument();
      expect(screen.getByText(/custo|cost/i)).toBeInTheDocument();
    });
  });
});
