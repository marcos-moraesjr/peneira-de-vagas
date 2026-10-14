import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { CONFIG, mockApi, renderWithClient } from "./test/mockApi";

const routes = {
  "GET /api/health": { status: "ok", db: "ok" },
  "GET /api/config": CONFIG,
  "GET /api/keywords": [],
  "GET /api/jobs": { items: [], total: 0 },
  "GET /api/runs": [],
};

describe("App", () => {
  it("abre na tela Vagas e alterna para Execuções", async () => {
    const user = userEvent.setup();
    mockApi(routes);
    renderWithClient(<App />);
    expect(await screen.findByRole("tab", { name: "Vagas", selected: true })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Execuções" }));
    expect(await screen.findByText(/nenhuma execução ainda/i)).toBeInTheDocument();
  });

  it("indica API e banco ok", async () => {
    mockApi(routes);
    renderWithClient(<App />);
    expect(await screen.findByText(/API: ok · banco: ok/)).toBeInTheDocument();
  });

  it("indica API indisponível", async () => {
    mockApi({ ...routes, "GET /api/health": { status: 500, json: {} } });
    renderWithClient(<App />);
    expect(await screen.findByText(/API indisponível/)).toBeInTheDocument();
  });
});
