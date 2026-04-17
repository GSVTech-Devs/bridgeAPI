import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../src/mocks/server";
import AdminMetricsPage from "../../src/app/admin/metrics/page";

// Recharts usa ResizeObserver que não existe no jsdom; stub silencioso
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe("AdminMetricsPage", () => {
  it("shows loading state initially", () => {
    render(<AdminMetricsPage />);
    expect(screen.getByText(/carregando/i)).toBeInTheDocument();
  });

  it("renders total requests after loading", async () => {
    render(<AdminMetricsPage />);
    await waitFor(() => {
      // toLocaleString() format varies by locale (en-US: "8,400", pt-BR: "8.400")
      expect(screen.getByText(/8[.,]?400/)).toBeInTheDocument();
    });
  });

  it("renders billable requests count", async () => {
    render(<AdminMetricsPage />);
    await waitFor(() => {
      expect(screen.getByText(/7[.,]?800/)).toBeInTheDocument();
    });
  });

  it("renders average latency rounded to ms", async () => {
    render(<AdminMetricsPage />);
    await waitFor(() => {
      // avg_latency_ms: 64.0 → Math.round = 64
      expect(screen.getByText(/64ms/)).toBeInTheDocument();
    });
  });

  it("exibe success rate corretamente como 100 - (error_rate * 100)", async () => {
    // NOTA: AdminMetricsPage faz `errorRate = metrics.error_rate * 100`.
    // O handler padrão tem error_rate: 0.012 (1.2% como fração).
    // Portanto: errorRate = 1.2 → successRate = 98.80%.
    //
    // Se esse teste falhar com "0.00%", significa que o handler retorna
    // error_rate como percentual (ex.: 1.2 = 120%) e o componente está
    // interpretando errado — comportamento idêntico ao MetricsDashboard
    // do cliente que não multiplica por 100.
    render(<AdminMetricsPage />);
    await waitFor(() => {
      expect(screen.getByText(/98\.80%/)).toBeInTheDocument();
    });
  });

  it("renders 'Total API Requests' section heading", async () => {
    render(<AdminMetricsPage />);
    await waitFor(() => {
      expect(screen.getByText(/total api requests/i)).toBeInTheDocument();
    });
  });

  it("renders Avg. Latency section", async () => {
    render(<AdminMetricsPage />);
    await waitFor(() => {
      expect(screen.getByText(/avg.*latency/i)).toBeInTheDocument();
    });
  });

  it("renders error ratio section", async () => {
    render(<AdminMetricsPage />);
    await waitFor(() => {
      expect(screen.getByText(/error ratio/i)).toBeInTheDocument();
    });
  });

  it("shows error alert when API call fails", async () => {
    server.use(
      http.get("http://localhost:8000/metrics/admin", () =>
        HttpResponse.json({ detail: "Forbidden" }, { status: 403 })
      )
    );
    render(<AdminMetricsPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("renders health distribution section", async () => {
    render(<AdminMetricsPage />);
    await waitFor(() => {
      expect(screen.getByText(/health distribution/i)).toBeInTheDocument();
    });
  });
});
