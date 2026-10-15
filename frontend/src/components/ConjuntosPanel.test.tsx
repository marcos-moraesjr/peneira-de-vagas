import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { CONFIG, mockApi, renderWithClient } from "../test/mockApi";
import { ConjuntosPanel } from "./ConjuntosPanel";

type Conjunto = { id: number; nome: string; ativo: boolean };

const mecanica: Conjunto = { id: 1, nome: "Mecânica", ativo: true };
const tecnologia: Conjunto = { id: 2, nome: "Tecnologia", ativo: false };

function setup(initial: Conjunto[], extra: Record<string, unknown> = {}) {
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
    "POST /api/conjuntos/1/copiar": (body: unknown) => {
      const copia = { id: 11, nome: (body as { nome: string }).nome, ativo: true };
      items = [...items.map((c) => ({ ...c, ativo: false })), copia];
      return { status: 201, json: copia };
    },
    "PATCH /api/conjuntos/1": (body: unknown) => {
      items = items.map((c) => (c.id === 1 ? { ...c, nome: (body as { nome: string }).nome } : c));
      return items[0];
    },
    ...extra,
    "DELETE /api/conjuntos/1": () => {
      items = items.filter((c) => c.id !== 1);
      return { status: 204 };
    },
  });
  renderWithClient(<ConjuntosPanel />);
  return api;
}

describe("ConjuntosPanel", () => {
  it("mostra os conjuntos em tabela e permite ativar uma linha pelo botao", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    expect(await screen.findByRole("table", { name: "Conjuntos de busca" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Mecânica está ativo" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Selecionar Tecnologia" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/conjuntos/2/ativar")).toBe(true));
  });

  it("remove o botao de copiar das linhas e oferece a copia no cadastro", async () => {
    setup([mecanica, tecnologia]);
    expect(await screen.findByRole("button", { name: "Excluir Mecânica" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copiar Mecânica" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Copiar palavras de")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Começar vazio" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Mecânica" })).toBeInTheDocument();
  });

  it("clica no nome para editar inline e salva o novo nome", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    await user.click(await screen.findByRole("button", { name: "Editar Mecânica" }));
    const input = screen.getByLabelText("Nome do conjunto Mecânica");
    await user.clear(input);
    await user.type(input, "Engenharia mecânica{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/api/conjuntos/1")?.body).toEqual({ nome: "Engenharia mecânica" }));
  });

  it("lista os conjuntos com o ativo selecionado", async () => {
    setup([mecanica, tecnologia]);
    expect(await screen.findByRole("table", { name: "Conjuntos de busca" })).toBeInTheDocument();
    const ativo = await screen.findByRole("button", { name: "Mecânica está ativo" });
    const selecionar = screen.getByRole("button", { name: "Selecionar Tecnologia" });
    expect(ativo).toHaveClass("w-24");
    expect(selecionar).toHaveClass("w-24");
    expect(screen.getByRole("button", { name: "Selecionar Tecnologia" })).toBeInTheDocument();
  });

  it("trocar o conjunto ativa o escolhido", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    await screen.findByRole("button", { name: "Selecionar Tecnologia" });
    await user.click(screen.getByRole("button", { name: "Selecionar Tecnologia" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/conjuntos/2/ativar")).toBe(true));
    await waitFor(() => expect(screen.getByRole("button", { name: "Tecnologia está ativo" })).toBeInTheDocument());
  });

  it("cria um conjunto novo e limpa o campo", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica]);
    const input = await screen.findByLabelText("Novo conjunto");
    await user.type(input, "Tecnologia{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/conjuntos")?.body).toEqual({ nome: "Tecnologia" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Tecnologia está ativo" })).toBeInTheDocument());
    expect(input).toHaveValue("");
  });

  it("exclui o conjunto ativo depois de confirmar", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = setup([mecanica, tecnologia]);
    const excluir = await screen.findByRole("button", { name: "Excluir Mecânica" });
    expect(excluir).toHaveClass("bg-erro-bg", "text-erro-fg");
    await user.click(excluir);
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/conjuntos/1")).toBe(true));
  });

  it("com um só conjunto, não dá para excluir", async () => {
    setup([mecanica]);
    expect(await screen.findByRole("button", { name: "Excluir Mecânica" })).toBeDisabled();
  });

  it("renomeia o conjunto ativo: abre com o nome atual, envia o novo e volta ao seletor", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    await user.click(await screen.findByRole("button", { name: "Editar Mecânica" }));
    const input = screen.getByLabelText("Nome do conjunto Mecânica");
    expect(input).toHaveValue("Mecânica");
    await user.clear(input);
    await user.type(input, "Engenharia mecânica{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/api/conjuntos/1")?.body).toEqual({ nome: "Engenharia mecânica" }));
    expect(await screen.findByRole("button", { name: "Editar Engenharia mecânica" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Nome do conjunto Mecânica")).not.toBeInTheDocument();
  });

  it("cancelar a renomeação não envia nada", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica]);
    await user.click(await screen.findByRole("button", { name: "Editar Mecânica" }));
    await user.type(screen.getByLabelText("Nome do conjunto Mecânica"), "x");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("button", { name: "Mecânica está ativo" })).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
  });

  it("nome recusado pelo servidor aparece no aviso e mantém a edição aberta", async () => {
    const user = userEvent.setup();
    setup([mecanica, tecnologia], { "PATCH /api/conjuntos/1": { status: 422, json: { detail: "Esse conjunto já existe: 'Tecnologia'" } } });
    await user.click(await screen.findByRole("button", { name: "Editar Mecânica" }));
    const input = screen.getByLabelText("Nome do conjunto Mecânica");
    await user.clear(input);
    await user.type(input, "Tecnologia{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Esse conjunto já existe");
    expect(screen.getByLabelText("Nome do conjunto Mecânica")).toBeInTheDocument();
  });

  it("copia um conjunto existente ao cadastrar e ativa a cópia", async () => {
    const user = userEvent.setup();
    const { calls } = setup([mecanica, tecnologia]);
    const input = await screen.findByLabelText("Novo conjunto");
    await screen.findByRole("option", { name: "Mecânica" });
    await user.selectOptions(screen.getByLabelText("Copiar palavras de"), "1");
    await user.type(input, "Mecânica júnior{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/api/conjuntos/1/copiar")?.body).toEqual({ nome: "Mecânica júnior" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Mecânica júnior está ativo" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Editar Mecânica júnior" })).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("nome da cópia recusado pelo servidor aparece no aviso e mantém a edição aberta", async () => {
    const user = userEvent.setup();
    setup([mecanica, tecnologia], { "POST /api/conjuntos/1/copiar": { status: 422, json: { detail: "Esse conjunto já existe: 'Mecânica (cópia)'" } } });
    const input = await screen.findByLabelText("Novo conjunto");
    await screen.findByRole("option", { name: "Mecânica" });
    await user.selectOptions(screen.getByLabelText("Copiar palavras de"), "1");
    await user.type(input, "Mecânica (cópia){Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Esse conjunto já existe");
    expect(screen.getByLabelText("Novo conjunto")).toHaveValue("Mecânica (cópia)");
  });
});
