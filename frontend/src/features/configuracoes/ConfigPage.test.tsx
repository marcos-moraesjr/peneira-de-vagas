import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CONFIG, mockApi, renderWithClient } from "../../test/mockApi";
import { ConfigPage } from "./ConfigPage";

function setup(put: unknown = (body: unknown) => body) {
  const api = mockApi({ "GET /api/config": CONFIG, "PUT /api/config": put });
  renderWithClient(<ConfigPage />);
  return api;
}

describe("ConfigPage", () => {
  it("mostra a configuração em vigor nos campos", async () => {
    setup();
    expect(await screen.findByLabelText("Pontuação mínima para aparecer")).toHaveValue("3");
    expect(screen.getByLabelText("Pausa máxima (s)")).toHaveValue("6");
  });

  it("nomeia os grupos conforme o propósito e explica ritmo e interface", async () => {
    setup();
    for (const nome of ["Rankeamento de vagas", "Limites de busca", "Ritmo e navegador", "Interface"]) {
      expect(await screen.findByRole("region", { name: nome })).toBeInTheDocument();
    }
    expect(screen.queryByRole("region", { name: "Ritmo de buscas" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Navegador" })).not.toBeInTheDocument();
    expect(screen.getByText("Menor espera entre uma ação e outra no navegador.")).toBeInTheDocument();
    expect(screen.getByText("Quantidade de vagas exibidas por página na lista.")).toBeInTheDocument();
  });

  it("ritmo e navegador são um só card, com controles deslizantes no lugar de campos de texto", async () => {
    setup();
    const card = within(await screen.findByRole("region", { name: "Ritmo e navegador" }));
    for (const nome of ["Pausa mínima (s)", "Pausa máxima (s)", "Rolagem mínima (s)", "Rolagem máxima (s)", "Tentativas para abrir o painel da vaga", "Intervalo entre tentativas (s)"]) {
      expect(card.getByRole("slider", { name: nome })).toBeInTheDocument();
    }
    expect(card.getByRole("checkbox", { name: /buscar as plataformas ao mesmo tempo/i })).toBeInTheDocument();
    expect(card.queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(card.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByTestId("valor-ritmo.pausa_min_s")).toHaveTextContent("2");
  });

  it("não oferece localidade nem modalidade (o filtro fica só no config.toml)", async () => {
    setup();
    await screen.findByLabelText("Pontuação mínima para aparecer");
    expect(screen.queryByLabelText("Localidades")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Adicionar localidade" })).not.toBeInTheDocument();
    for (const nome of ["Remoto", "Híbrido", "Presencial"]) expect(screen.queryByRole("checkbox", { name: nome })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Janela de recência (horas)")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Janela de recência (dias)")).not.toBeInTheDocument();
  });

  it("pesos e pontuação mínima são controles deslizantes com o valor à vista", async () => {
    setup();
    for (const nome of ["Pontos por palavra-chave no título", "Pontos por palavra-chave na descrição", "Pontuação mínima para aparecer"]) {
      expect(await screen.findByRole("slider", { name: nome })).toBeInTheDocument();
    }
    expect(screen.getByRole("slider", { name: "Pontos por palavra-chave no título" })).toHaveValue("3");
    expect(screen.getByTestId("valor-filtro.peso_titulo")).toHaveTextContent("3");
  });

  it("deixa apenas o limite de páginas por palavra-chave ajustável", async () => {
    const { calls } = setup();
    await screen.findByRole("slider", { name: "Páginas abertas por palavra-chave (em cada fonte)" });
    expect(screen.queryByLabelText("Tamanho máximo da palavra-chave")).not.toBeInTheDocument();
    expect(screen.queryByRole("slider", { name: "Palavras-chave por busca (máximo)" })).not.toBeInTheDocument();
    const paginas = screen.getByRole("slider", { name: "Páginas abertas por palavra-chave (em cada fonte)" });
    expect(paginas).toHaveValue("3");
    expect(paginas).toHaveAttribute("min", "1");
    fireEvent.change(paginas, { target: { value: "5" } });
    expect(screen.getByTestId("valor-limites.max_paginas_por_termo")).toHaveTextContent("5");
    fireEvent.pointerUp(paginas);
    await screen.findByText(/configuração salva/i);
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toEqual({
      ...CONFIG,
      limites: { max_paginas_por_termo: 5 },
    });
  });

  it("não tem o recalcular pontuação: o botão fica na aba Vagas", async () => {
    setup();
    await screen.findByRole("slider", { name: "Pontuação mínima para aparecer" });
    expect(screen.queryByRole("button", { name: "Recalcular pontuação" })).not.toBeInTheDocument();
  });

  it("restaurar padrões iniciais pede confirmação, chama a API e mostra os valores devolvidos", async () => {
    const user = userEvent.setup();
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const padroes = { ...CONFIG, filtro: { ...CONFIG.filtro, min_score: 5 } };
    const api = mockApi({ "GET /api/config": CONFIG, "POST /api/config/restaurar-padroes": padroes });
    renderWithClient(<ConfigPage />);
    const botao = await screen.findByRole("button", { name: "Restaurar padrões iniciais" });
    await user.click(botao);
    expect(confirmar).toHaveBeenCalledTimes(1);
    expect(api.calls.some((c) => c.path === "/api/config/restaurar-padroes")).toBe(false);
    confirmar.mockReturnValue(true);
    await user.click(botao);
    await waitFor(() => expect(screen.getByTestId("valor-filtro.min_score")).toHaveTextContent("5"));
    expect(api.calls.filter((c) => c.method === "POST" && c.path === "/api/config/restaurar-padroes")).toHaveLength(1);
  });

  it("não tem botões Salvar nem Descartar: o salvamento é automático", async () => {
    setup();
    await screen.findByRole("slider", { name: "Pontuação mínima para aparecer" });
    expect(screen.queryByRole("button", { name: "Salvar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Descartar" })).not.toBeInTheDocument();
  });

  it("sair de um campo sem alterar nada não envia nada", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("slider", { name: "Pausa mínima (s)" }));
    await user.tab();
    expect(calls.find((c) => c.method === "PUT")).toBeUndefined();
  });

  it("envia a configuração completa, com números, e confirma", async () => {
    const { calls } = setup();
    fireEvent.change(await screen.findByRole("slider", { name: "Pontuação mínima para aparecer" }), { target: { value: "5" } });
    expect(screen.getByTestId("valor-filtro.min_score")).toHaveTextContent("5");
    expect(calls.find((c) => c.method === "PUT")).toBeUndefined();
    fireEvent.keyUp(screen.getByRole("slider", { name: "Pontuação mínima para aparecer" }), { key: "ArrowRight" });
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT");
    // busca.localidades e busca.modalidade não estão na tela, mas seguem no corpo, como o servidor devolveu
    expect(put?.body).toEqual({ ...CONFIG, filtro: { ...CONFIG.filtro, min_score: 5 } });
  });

  it("salva ao soltar o controle deslizante do ritmo", async () => {
    const { calls } = setup();
    const campo = await screen.findByRole("slider", { name: "Pausa mínima (s)" });
    fireEvent.change(campo, { target: { value: "4" } });
    expect(calls.find((c) => c.method === "PUT")).toBeUndefined();
    fireEvent.keyUp(campo, { key: "ArrowRight" });
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ ...CONFIG, ritmo: { ...CONFIG.ritmo, pausa_min_s: 4 } });
  });

  it("ativa a busca em paralelo por plataforma e envia navegador.abas_paralelas", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const opcao = await screen.findByRole("checkbox", { name: /buscar as plataformas ao mesmo tempo/i });
    expect(opcao).not.toBeChecked();
    await user.click(opcao);
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ ...CONFIG, navegador: { ...CONFIG.navegador, abas_paralelas: true } });
  });

  it("edita as tentativas e o intervalo de espera para abrir o painel da vaga", async () => {
    const { calls } = setup();
    const tentativas = await screen.findByRole("slider", { name: /tentativas para abrir o painel/i });
    expect(tentativas).toHaveValue("3");
    fireEvent.change(tentativas, { target: { value: "5" } });
    fireEvent.keyUp(tentativas, { key: "ArrowRight" });
    expect(await screen.findByText(/configuração salva/i)).toBeInTheDocument();
    const intervalo = screen.getByRole("slider", { name: /intervalo entre tentativas/i });
    expect(intervalo).toHaveValue("15");
    fireEvent.change(intervalo, { target: { value: "20" } });
    fireEvent.keyUp(intervalo, { key: "ArrowRight" });
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(2));
    expect(calls.filter((c) => c.method === "PUT").at(-1)?.body).toEqual({
      ...CONFIG,
      navegador: { ...CONFIG.navegador, max_tentativas_painel: 5, intervalo_tentativa_painel_s: 20 },
    });
  });

  it("mostra o erro do backend e mantém o que foi digitado", async () => {
    setup({ status: 422, json: { detail: "Config inválida: pausa_min_s=9.0 (esperado <= pausa_max_s=6.0)" } });
    const campo = await screen.findByRole("slider", { name: "Pausa mínima (s)" });
    fireEvent.change(campo, { target: { value: "9" } });
    fireEvent.keyUp(campo, { key: "ArrowRight" });
    expect(await screen.findByText(/pausa_min_s=9.0/)).toBeInTheDocument();
    expect(campo).toHaveValue("9");
  });
});
