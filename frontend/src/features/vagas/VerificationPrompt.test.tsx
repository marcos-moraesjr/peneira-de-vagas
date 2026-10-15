import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, mockApi, renderWithClient } from "../../test/mockApi";
import { VerificationPrompt } from "./VerificationPrompt";

function setup(opts: { fontes: string[]; running?: boolean }) {
  let fontes = opts.fontes;
  const api = mockApi({
    "GET /api/config": CONFIG,
    "GET /api/verificacao": () => ({ fontes }),
    "POST /api/verificacao/indeed/confirmar": () => {
      fontes = [];
      return { status: 204 };
    },
  });
  renderWithClient(<VerificationPrompt running={opts.running ?? true} />);
  return api;
}

describe("VerificationPrompt", () => {
  it("sem fonte esperando não mostra nada", async () => {
    const { calls } = setup({ fontes: [] });
    await waitFor(() => expect(calls.some((c) => c.path === "/api/verificacao")).toBe(true));
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("avisa qual fonte pede verificação e confirma com POST, sumindo em seguida", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ fontes: ["indeed"] });
    expect(await screen.findByText(/Indeed/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Já concluí a verificação" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/verificacao/indeed/confirmar")).toBe(true));
    await waitFor(() => expect(screen.queryByRole("button")).not.toBeInTheDocument());
  });

  it("fora de uma execução não consulta o servidor", async () => {
    const { calls } = setup({ fontes: ["indeed"], running: false });
    await act(() => new Promise((resolve) => setTimeout(resolve, 120)));
    expect(calls.some((c) => c.path === "/api/verificacao")).toBe(false);
  });
});
