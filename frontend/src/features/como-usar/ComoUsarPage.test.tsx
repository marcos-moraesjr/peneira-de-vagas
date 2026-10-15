import { screen, within } from "@testing-library/react";
import { FAILURE_REASONS, describeFailure } from "../../lib/failures";
import { renderWithClient } from "../../test/mockApi";
import { ComoUsarPage } from "./ComoUsarPage";

describe("ComoUsarPage", () => {
  it("ensina os passos na ordem de uso", () => {
    renderWithClient(<ComoUsarPage />);
    const steps = within(screen.getByRole("list", { name: "Passos" })).getAllByRole("listitem");
    const titles = steps.map((step) => within(step).getByRole("heading").textContent);
    expect(titles).toEqual([
      "Abra o Chrome dedicado",
      "Entre nos sites (uma vez)",
      "Cadastre as palavras-chave",
      "Busque",
      "Leia os resultados",
    ]);
  });

  it("manda abrir o Chrome dedicado pelo botão do app e explica a porta de depuração", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText("Abrir Chrome dedicado", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/9222/)).toBeInTheDocument();
  });

  it("mantém o script como alternativa manual", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText(/scripts\\chrome-dedicado\.ps1/)).toBeInTheDocument();
  });

  it("avisa que sem o Chrome dedicado só a Gupy funciona", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText(/só a Gupy/i)).toBeInTheDocument();
  });

  it("explica o botão Buscar agora e a diferença entre vagas novas e vistas", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText(/Buscar agora/, { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/Não lidas/, { selector: "strong" })).toBeInTheDocument();
  });

  it("nunca pede para o usuário contornar bloqueios", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText(/não contorna/i)).toBeInTheDocument();
  });

  it("explica que a fonte espera a verificação manual e o botão de confirmação", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText("Já concluí a verificação", { selector: "strong" })).toBeInTheDocument();
    expect(screen.queryByText(/ela é encerrada e avisada/)).not.toBeInTheDocument();
  });

  it("não diz que a Gupy traz vagas antigas na primeira busca", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.queryByText(/vagas antigas/)).not.toBeInTheDocument();
  });

  it("diz que as plataformas podem buscar ao mesmo tempo", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText(/ao mesmo tempo/)).toBeInTheDocument();
  });

  it("tabela de problemas cobre todos os motivos de falha, com a mesma frase e ação da tela Vagas", () => {
    renderWithClient(<ComoUsarPage />);
    const table = screen.getByRole("table", { name: "Problemas comuns" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(FAILURE_REASONS.length);
    for (const reason of FAILURE_REASONS) {
      const { action } = describeFailure("linkedin", reason);
      expect(within(table).getByText(action)).toBeInTheDocument();
    }
  });

  it("explica o aviso de scanner a refazer", () => {
    renderWithClient(<ComoUsarPage />);
    expect(screen.getByText(/Copiar instrução para o Claude/)).toBeInTheDocument();
  });
});
