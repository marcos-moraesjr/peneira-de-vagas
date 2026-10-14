import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { CONFIG, mockApi, renderWithClient } from "../test/mockApi";
import { ConjuntosPanel } from "./ConjuntosPanel";

type Conjunto = { id: number; nome: string; ativo: boolean };

const mecanica: Conjunto = { id: 1, nome: "Mecânica", ativo: true };
const tecnologia: Conjunto = { id: 2, nome: "Tecnologia", ativo: false };

function setup(initial: Conjunto[]) {
  let items = [...initial];
  const api = mockApi({
    "GET /api/config": CONFIG,
    "GET /api/conjuntos": () => items,
    "POST /api/conjuntos": (body: unknown) => {
      const created = { id: 10, nome: (body as { nome: string }).nome, ativo: true };
      items = [...items.map((c) => ({ ...c, ativo: false })), created];
      return { status: 201, json: created };
    },
    "POST /api/conjuntos/2/ativar": () => {
      items = items.map((c) => ({ ...c, ativo: c.id === 2 }));
      return { status: 204 };
    },
    "DELETE /api/conjuntos/1": () => {
      items = items.filter((c) => c.id !== 1);
      return { status: 204 };
    },
  });
  renderWithClient(<ConjuntosPanel />);
  return api;
}

describe("ConjuntosPanel", () => {
  it("lista os conjuntos com o ativo selecionado", async () => {
    setup([mecanica, tecnologia]);
    const select = await screen.findByLabelText("Conjunto ativo");
    await waitFor(() => expect(select).toHaveValue("1"));
    expect(screen.getByRole("option", { name: "Tecnologia" })).toBeInTheDocument();
  });

  it("trocar o conjunto ativa o escolhido", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    await screen.findByRole("option", { name: "Tecnologia" });
    await user.selectOptions(screen.getByLabelText("Conjunto ativo"), "Tecnologia");
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/conjuntos/2/ativar")).toBe(true));
    await waitFor(() => expect(screen.getByLabelText("Conjunto ativo")).toHaveValue("2"));
  });

  it("cria um conjunto novo e limpa o campo", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica]);
    const input = await screen.findByLabelText("Novo conjunto");
    await user.type(input, "Tecnologia{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/conjuntos")?.body).toEqual({ nome: "Tecnologia" }));
    await waitFor(() => expect(screen.getByLabelText("Conjunto ativo")).toHaveValue("10"));
    expect(input).toHaveValue("");
  });

  it("exclui o conjunto ativo depois de confirmar", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup([mecanica, tecnologia]);
    await user.click(await screen.findByRole("button", { name: "Excluir conjunto" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/conjuntos/1")).toBe(true));
  });

  it("com um só conjunto, não dá para excluir", async () => {
    setup([mecanica]);
    expect(await screen.findByRole("button", { name: "Excluir conjunto" })).toBeDisabled();
  });
});
