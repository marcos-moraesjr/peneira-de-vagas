import { screen, within } from "@testing-library/react";
import { FAILURE_REASONS, describeFailure } from "../../lib/failures";
import { renderWithClient } from "../../test/mockApi";
import { TutorialPage } from "./TutorialPage";

describe("TutorialPage", () => {
  it("ensina os passos na ordem de uso", () => {
    renderWithClient(<TutorialPage />);
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
    renderWithClient(<TutorialPage />);
    expect(screen.getByText("Abrir Chrome dedicado", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/9222/)).toBeInTheDocument();
  });

  it("mantém o script como alternativa manual", () => {
    renderWithClient(<TutorialPage />);
    expect(screen.getByText(/scripts\\chrome-dedicado\.ps1/)).toBeInTheDocument();
  });

  it("avisa que sem o Chrome dedicado só a Gupy funciona", () => {
    renderWithClient(<TutorialPage />);
    expect(screen.getByText(/só a Gupy/i)).toBeInTheDocument();
  });

  it("explica o botão Buscar agora e a diferença entre vagas novas e vistas", () => {
    renderWithClient(<TutorialPage />);
    expect(screen.getByText(/Buscar agora/, { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/Não lidas/, { selector: "strong" })).toBeInTheDocument();
  });

  it("nunca pede para o usuário contornar bloqueios", () => {
    renderWithClient(<TutorialPage />);
    expect(screen.getByText(/não contorna/i)).toBeInTheDocument();
  });

  it("tabela de problemas cobre todos os motivos de falha, com a mesma frase e ação da tela Vagas", () => {
    renderWithClient(<TutorialPage />);
    const table = screen.getByRole("table", { name: "Problemas comuns" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(FAILURE_REASONS.length);
    for (const reason of FAILURE_REASONS) {
      const { action } = describeFailure("linkedin", reason);
      expect(within(table).getByText(action)).toBeInTheDocument();
    }
  });

  it("explica o aviso de scanner a refazer", () => {
    renderWithClient(<TutorialPage />);
    expect(screen.getByText(/Copiar instrução para o Claude/)).toBeInTheDocument();
  });
});
