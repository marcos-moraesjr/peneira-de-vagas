import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, mockApi, renderWithClient } from "../../test/mockApi";
import { ChromeStatus } from "./ChromeStatus";

function setup(opts: { aberto: boolean; openReply?: unknown }) {
  let aberto = opts.aberto;
  const api = mockApi({
    "GET /api/config": CONFIG,
    "GET /api/browser": () => ({ aberto }),
    "POST /api/browser/open":
      opts.openReply ??
      (() => {
        aberto = true;
        return { estado: "aberto" };
      }),
  });
  renderWithClient(<ChromeStatus />);
  return { api, abrirPorFora: () => (aberto = true) };
}

describe("ChromeStatus", () => {
  it("com o Chrome dedicado aberto só informa, sem botão", async () => {
    setup({ aberto: true });
    expect(await screen.findByText(/Chrome dedicado aberto/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Abrir Chrome dedicado/ })).not.toBeInTheDocument();
  });

  it("com o Chrome fechado explica o efeito e oferece o botão", async () => {
    setup({ aberto: false });
    expect(await screen.findByText(/Chrome dedicado fechado/)).toBeInTheDocument();
    expect(screen.getByText(/LinkedIn, Indeed e Google/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abrir Chrome dedicado" })).toBeEnabled();
  });

  it("clicar abre o Chrome pela API e passa a mostrar aberto", async () => {
    const user = userEvent.setup();
    const { api } = setup({ aberto: false });
    await user.click(await screen.findByRole("button", { name: "Abrir Chrome dedicado" }));
    await waitFor(() => expect(api.calls.some((c) => c.method === "POST" && c.path === "/api/browser/open")).toBe(true));
    expect(await screen.findByText(/Chrome dedicado aberto/)).toBeInTheDocument();
  });

  it("detecta sozinho que o Chrome foi aberto por fora (script ou à mão)", async () => {
    const { abrirPorFora } = setup({ aberto: false });
    await screen.findByText(/Chrome dedicado fechado/);
    abrirPorFora();
    expect(await screen.findByText(/Chrome dedicado aberto/)).toBeInTheDocument();
  });

  it("mostra a orientação da API quando o Chrome não é encontrado", async () => {
    const user = userEvent.setup();
    setup({ aberto: false, openReply: { status: 422, json: { detail: "Chrome não encontrado em ['x']. Ajuste chrome_paths no config.toml" } } });
    await user.click(await screen.findByRole("button", { name: "Abrir Chrome dedicado" }));
    expect(await screen.findByText(/Ajuste chrome_paths/)).toBeInTheDocument();
  });
});

describe("ChromeStatus — sem cópia de perfil", () => {
  it("não oferece copiar perfil nem consulta perfis, com o Chrome aberto ou fechado", async () => {
    const fechado = setup({ aberto: false });
    await screen.findByText(/Chrome dedicado fechado/);
    expect(screen.queryByText(/copiar perfil/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fechado.api.calls.some((c) => c.path.includes("/api/browser/profile"))).toBe(false);
  });
});
