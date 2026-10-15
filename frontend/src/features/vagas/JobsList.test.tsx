import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeJob } from "../../test/mockApi";
import { JobsList } from "./JobsList";

const JOBS = [
  makeJob(1, { localidade: "Campinas, São Paulo", cidade: "Campinas", estado: "SP", modalidade: "hibrido", palavra_chave: "Projetista", publicada_em: "2026-10-08T11:04:27.057Z", pontos: 4 }),
  makeJob(2, { fonte: "linkedin", empresa: "", localidade: "", publicada_em: null, visto: true }),
];

describe("JobsList (tabela)", () => {
  it("mostra as colunas Vaga, Empresa, Palavra-chave, Cidade, Estado, Modalidade, Publicada, Encontrada, Plataforma e Pontos", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={null} onSort={() => {}} />);
    const names = screen.getAllByRole("columnheader").map((header) => header.textContent?.replace(/[▲▼↕]/g, ""));
    expect(names).toEqual(["Ações", "Vaga", "Empresa", "Palavra-chave", "Cidade", "Estado", "Modalidade", "Publicada", "Encontrada", "Plataforma", "Pontos"]);
  });

  it("preenche uma linha por vaga com cidade, estado e data de publicação", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={null} onSort={() => {}} />);
    const row = screen.getByRole("row", { name: /Engenheiro Mecânico 1/ });
    expect(within(row).getByRole("link", { name: "Engenheiro Mecânico 1" })).toHaveAttribute("href", "https://vagas.example/1");
    expect(within(row).getByText("ACME")).toBeInTheDocument();
    expect(within(row).getByText("Projetista")).toBeInTheDocument();
    expect(within(row).getByText("Campinas")).toBeInTheDocument();
    expect(within(row).getByText("SP")).toBeInTheDocument();
    expect(within(row).getByText("Híbrido")).toBeInTheDocument();
    expect(within(row).getByText("08/10/2026")).toBeInTheDocument();
    expect(within(row).getByText("4")).toBeInTheDocument();
  });

  it("campos que a fonte não informa aparecem como traço, nunca vazios", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={null} onSort={() => {}} />);
    const row = screen.getByRole("row", { name: /Engenheiro Mecânico 2/ });
    expect(within(row).getAllByText("—")).toHaveLength(6); // empresa, palavra-chave, cidade, estado, modalidade e publicada
  });

  it("vaga não lida é destacada (ponto e cor de fundo) e lida não; não há botão de marcar", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={null} onSort={() => {}} />);
    expect(screen.getAllByLabelText("Vaga nova")).toHaveLength(1);
    expect(screen.getByRole("row", { name: /Engenheiro Mecânico 1/ })).toHaveClass("bg-sinal-ponto/10");
    expect(screen.getByRole("row", { name: /Engenheiro Mecânico 2/ })).not.toHaveClass("bg-sinal-ponto/10");
    expect(screen.queryByRole("button", { name: /Marcar como/ })).not.toBeInTheDocument();
  });

  it("cabeçalhos de dados são botões de ordenação", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={null} onSort={() => {}} />);
    for (const nome of ["Vaga", "Empresa", "Palavra-chave", "Cidade", "Estado", "Modalidade", "Publicada", "Encontrada", "Plataforma", "Pontos"]) {
      expect(screen.getByRole("button", { name: new RegExp(`^${nome}`) })).toBeInTheDocument();
    }
  });

  it("clicar em Palavra-chave pede a ordenação por palavra_chave", async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={null} onSort={onSort} />);
    await user.click(screen.getByRole("button", { name: /^Palavra-chave/ }));
    expect(onSort).toHaveBeenCalledWith("palavra_chave");
  });

  it("clicar no cabeçalho pede a ordenação por aquela coluna", async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={null} onSort={onSort} />);
    await user.click(screen.getByRole("button", { name: /^Cidade/ }));
    expect(onSort).toHaveBeenCalledWith("cidade");
  });

  it("indica a coluna e a direção ativas com aria-sort", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} onExcluir={() => {}} sort={{ column: "empresa", direction: "desc" }} onSort={() => {}} />);
    expect(screen.getByRole("columnheader", { name: /^Empresa/ })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: /^Modalidade/ })).toHaveAttribute("aria-sort", "none");
  });
});
