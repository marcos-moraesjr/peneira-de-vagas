import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeJob } from "../../test/mockApi";
import { JobsList } from "./JobsList";

const JOBS = [
  makeJob(1, { localidade: "Campinas, São Paulo", publicada_em: "2026-10-08T11:04:27.057Z", pontos: 4 }),
  makeJob(2, { fonte: "linkedin", empresa: "", localidade: "", publicada_em: null, visto: true }),
];

describe("JobsList (tabela)", () => {
  it("mostra as colunas Vaga, Empresa, Localidade, Publicada, Encontrada, Plataforma e Pontos", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} sort={null} onSort={() => {}} />);
    const names = screen.getAllByRole("columnheader").map((header) => header.textContent?.replace(/[▲▼↕]/g, ""));
    expect(names).toEqual(["Vaga", "Empresa", "Localidade", "Publicada", "Encontrada", "Plataforma", "Pontos", "Ações"]);
  });

  it("preenche uma linha por vaga com localidade e data de publicação", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} sort={null} onSort={() => {}} />);
    const row = screen.getByRole("row", { name: /Engenheiro Mecânico 1/ });
    expect(within(row).getByRole("link", { name: "Engenheiro Mecânico 1" })).toHaveAttribute("href", "https://vagas.example/1");
    expect(within(row).getByText("ACME")).toBeInTheDocument();
    expect(within(row).getByText("Campinas, São Paulo")).toBeInTheDocument();
    expect(within(row).getByText("08/10/2026")).toBeInTheDocument();
    expect(within(row).getByText("4")).toBeInTheDocument();
  });

  it("campos que a fonte não informa aparecem como traço, nunca vazios", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} sort={null} onSort={() => {}} />);
    const row = screen.getByRole("row", { name: /Engenheiro Mecânico 2/ });
    expect(within(row).getAllByText("—")).toHaveLength(3); // empresa, localidade e publicada
  });

  it("vaga nova é destacada e o botão alterna vista/nova", async () => {
    const user = userEvent.setup();
    const onSeen = vi.fn();
    render(<JobsList jobs={JOBS} onSeen={onSeen} sort={null} onSort={() => {}} />);
    expect(screen.getAllByLabelText("Vaga nova")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Marcar como vista" }));
    expect(onSeen).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }), true);
    await user.click(screen.getByRole("button", { name: "Marcar como nova" }));
    expect(onSeen).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }), false);
  });

  it("cabeçalhos de dados são botões de ordenação; Ações não", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} sort={null} onSort={() => {}} />);
    for (const nome of ["Vaga", "Empresa", "Localidade", "Publicada", "Encontrada", "Plataforma", "Pontos"]) {
      expect(screen.getByRole("button", { name: new RegExp(`^${nome}`) })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: /^Ações/ })).not.toBeInTheDocument();
  });

  it("clicar no cabeçalho pede a ordenação por aquela coluna", async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(<JobsList jobs={JOBS} onSeen={() => {}} sort={null} onSort={onSort} />);
    await user.click(screen.getByRole("button", { name: /^Localidade/ }));
    expect(onSort).toHaveBeenCalledWith("localidade");
  });

  it("indica a coluna e a direção ativas com aria-sort", () => {
    render(<JobsList jobs={JOBS} onSeen={() => {}} sort={{ column: "empresa", direction: "desc" }} onSort={() => {}} />);
    expect(screen.getByRole("columnheader", { name: /^Empresa/ })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: /^Localidade/ })).toHaveAttribute("aria-sort", "none");
  });
});
