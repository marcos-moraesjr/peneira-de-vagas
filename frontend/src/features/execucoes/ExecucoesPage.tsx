import { useCallback, useEffect, useState } from "react";
import { useClearRuns, useConfig, useDeleteRun, useDocumentationInstruction, useRuns, useScanners } from "../../api/hooks";
import type { Config, Run, Scanner } from "../../api/types";
import { CopyButton } from "../../components/CopyButton";
import { ErrorBox } from "../../components/ErrorBox";
import { buttonDanger, buttonSecondary, card, inputClass } from "../../components/ui";
import { describeFailure, sourceLabel } from "../../lib/failures";
import { formatDate, formatDateTime, formatDuration } from "../../lib/format";

function SourcesTable({ run }: { run: Run }) {
  return (
    <table className="mt-2 w-full text-left text-sm">
      <thead className="text-rotulo uppercase text-grafite-500">
        <tr className="text-xs uppercase text-grafite-500">
          <th className="py-1">Fonte</th>
          <th>Resultado</th>
          <th className="text-right">Lidas</th>
          <th className="text-right">Aprovadas</th>
          <th className="text-right">Novas</th>
          <th className="text-right">Scanner</th>
        </tr>
      </thead>
      <tbody>
        {run.fontes.map((source) => (
          <tr key={source.fonte} className="border-t border-linha-2">
            <td className="py-1 font-medium">{sourceLabel(source.fonte)}</td>
            <td>
              {source.status === "falha"
                ? describeFailure(source.fonte, source.motivo ?? "erro_interno").message
                : source.status === "ok"
                  ? "ok"
                  : source.status}
            </td>
            <td className="text-right text-dado">{source.lidas}</td>
            <td className="text-right text-dado">{source.aprovadas}</td>
            <td className="text-right text-dado">{source.novas}</td>
            <td className="text-right text-dado">{source.scanner_versao ? `v${source.scanner_versao}` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type SortKey = "id" | "inicio" | "duracao" | "resultado";
type SortState = { key: SortKey; dir: "asc" | "desc" };

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "id", label: "Execução" },
  { key: "inicio", label: "Início" },
  { key: "duracao", label: "Duração" },
  { key: "resultado", label: "Resultado" },
];

function failedCount(run: Run): number {
  return run.fontes.filter((source) => source.status === "falha").length;
}

function sortValue(run: Run, key: SortKey): number {
  switch (key) {
    case "id":
      return run.id;
    case "inicio":
      return new Date(run.inicio).getTime();
    case "duracao":
      return run.fim ? new Date(run.fim).getTime() - new Date(run.inicio).getTime() : Number.POSITIVE_INFINITY;
    case "resultado":
      return run.status === "executando" ? -1 : failedCount(run);
  }
}

function sortRuns(runs: Run[], { key, dir }: SortState): Run[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...runs].sort((a, b) => sign * (sortValue(a, key) - sortValue(b, key)) || b.id - a.id);
}

function resultLabel(run: Run): string {
  const failed = failedCount(run);
  return run.status === "executando" ? "em andamento" : failed ? `${failed} fonte(s) com falha` : "sem falhas";
}

function RunDetail({ run, onClose }: { run: Run; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-grafite-900/40 p-4" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-detail-title"
        className={`${card} max-h-full w-full max-w-3xl overflow-auto`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="run-detail-title" className="text-titulo text-grafite-900">
              Execução #{run.id}
            </h2>
            <p className="text-sm text-grafite-500">
              {formatDateTime(run.inicio)} · {formatDuration(run.inicio, run.fim)} · {resultLabel(run)}
            </p>
          </div>
          <button type="button" className={buttonSecondary} onClick={onClose}>
            Fechar
          </button>
        </div>
        <SourcesTable run={run} />
      </section>
    </div>
  );
}

type RunsTableProps = {
  runs: Run[];
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  disabled: boolean;
  onClear: () => void;
  clearDisabled: boolean;
};

function RunsTable({ runs, onSelect, onDelete, disabled, onClear, clearDisabled }: RunsTableProps) {
  const [sort, setSort] = useState<SortState>({ key: "id", dir: "desc" });
  const toggle = (key: SortKey) =>
    setSort((current) => ({ key, dir: current.key === key && current.dir === "asc" ? "desc" : "asc" }));
  return (
    <section className={`${card} overflow-x-auto`} aria-labelledby="runs-history-title">
      <h2 id="runs-history-title" className="text-titulo text-grafite-900">Histórico de execuções</h2>
      <p className="mb-3 text-xs text-grafite-500">
        Consulte as buscas já realizadas e abra uma execução para ver o resultado de cada fonte.
      </p>
      <table aria-label="Execuções" className="w-full text-left text-sm">
        <thead className="text-rotulo uppercase text-grafite-500">
          <tr className="text-xs uppercase text-grafite-500">
            {COLUMNS.map(({ key, label }) => (
              <th
                key={key}
                scope="col"
                className="py-1"
                aria-sort={sort.key === key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
              >
                <button type="button" onClick={() => toggle(key)} className="uppercase">
                  {label}
                  <span aria-hidden="true">{sort.key === key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}</span>
                </button>
              </th>
            ))}
            <th scope="col" className="py-1 text-right">
              <div className="flex justify-end">
                <button type="button" className={buttonDanger} disabled={clearDisabled} onClick={onClear}>
                  Limpar execuções
                </button>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          {sortRuns(runs, sort).map((run) => (
            <tr key={run.id} className="border-t border-linha-2 hover:bg-painel">
              <td className="py-1">
                <button type="button" onClick={() => onSelect(run.id)} className="font-semibold">
                  Execução #{run.id}
                </button>
              </td>
              <td>{formatDateTime(run.inicio)}</td>
              <td className="text-grafite-500">{formatDuration(run.inicio, run.fim)}</td>
              <td className={failedCount(run) ? "text-atencao-fg" : "text-grafite-500"}>{resultLabel(run)}</td>
              <td className="text-right">
                <button
                  type="button"
                  className={buttonDanger}
                  aria-label={`Excluir execução #${run.id}`}
                  disabled={disabled || run.status === "executando"}
                  onClick={() => onDelete(run.id)}
                >
                  Excluir
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ConfigView({ config }: { config: Config }) {
  const rows: [string, string][] = [
    ["Localidades", config.busca.localidades.join(", ") || "qualquer"],
    ["Modalidade", config.busca.modalidade.join(", ") || "qualquer"],
    ["Janela padrão da busca", `${config.busca.janela_dias} dias`],
    ["Pontos por termo no título / na descrição", `${config.filtro.peso_titulo} / ${config.filtro.peso_descricao}`],
    ["Pontuação mínima", String(config.filtro.min_score)],
    ["Páginas abertas por palavra-chave (por fonte)", String(config.limites.max_paginas_por_termo)],
    ["Pausa entre ações", `${config.ritmo.pausa_min_s}–${config.ritmo.pausa_max_s} s`],
  ];
  return (
    <section className={card}>
      <h2 className="mb-2 text-titulo text-grafite-900">Configuração em vigor</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-grafite-500">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-grafite-500">
        Para alterar, edite config.toml. Palavras-chave e exclusões são editadas na tela Vagas.
      </p>
    </section>
  );
}

const SCANNER_STATUS: Record<string, string> = { ok: "Em dia", atencao: "Atenção", refazer: "Refazer" };

function ScannersTable({ scanners }: { scanners: Scanner[] }) {
  return (
    <section className={card}>
      <h2 className="mb-2 text-titulo text-grafite-900">Scanners (gerados pelo Claude)</h2>
      <table aria-label="Scanners" className="w-full text-left text-sm">
        <thead className="text-rotulo uppercase text-grafite-500">
          <tr className="text-xs uppercase text-grafite-500">
            <th className="py-1">Fonte</th>
            <th>Versão</th>
            <th>Explorado em</th>
            <th>Gerado por</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {scanners.map((scanner) => (
            <tr key={scanner.fonte} className="border-t border-linha-2" title={scanner.mensagem}>
              <td className="py-1 font-medium">{sourceLabel(scanner.fonte)}</td>
              <td>v{scanner.versao}</td>
              <td>{formatDate(scanner.explorado_em)}</td>
              <td>{scanner.gerado_por}</td>
              <td className={scanner.status === "ok" ? "" : "font-medium text-atencao-fg"}>
                {SCANNER_STATUS[scanner.status] ?? scanner.status}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

const DOC_SOURCES = ["linkedin", "indeed", "gupy"];

/** Gera a instrução para o Claude Code refazer a documentação das plataformas (todas ou uma). */
function DocumentationPanel() {
  const [fonte, setFonte] = useState("");
  const generate = useDocumentationInstruction();
  return (
    <section className={`${card} space-y-3`}>
      <h2 className="text-titulo text-grafite-900">Refazer a documentação das plataformas</h2>
      <p className="text-xs text-grafite-500">
        Gera uma instrução para colar numa sessão do Claude Code neste repositório: ele explora as plataformas de novo
        e atualiza docs/EXPLORACAO_PLATAFORMAS.md, sem mexer no código.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-grafite-700">
          Plataforma
          <select value={fonte} onChange={(event) => setFonte(event.target.value)} className={inputClass}>
            <option value="">Todas as plataformas</option>
            {DOC_SOURCES.map((source) => (
              <option key={source} value={source}>
                {sourceLabel(source)}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className={buttonSecondary} disabled={generate.isPending} onClick={() => generate.mutate(fonte)}>
          Gerar instrução para refazer a documentação
        </button>
      </div>
      {generate.error && <ErrorBox message={generate.error.message} />}
      {generate.data && (
        <div className="space-y-2">
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-grafite-900 p-3 text-xs text-painel">
            {generate.data.instrucao}
          </pre>
          <CopyButton text={generate.data.instrucao} />
        </div>
      )}
    </section>
  );
}

export function ExecucoesPage() {
  const runs = useRuns();
  const config = useConfig();
  const scanners = useScanners();
  const clear = useClearRuns();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const closeDetail = useCallback(() => setSelectedId(null), []);
  const selectedRun = runs.data?.find((run) => run.id === selectedId);
  const remove = useDeleteRun();
  const deleteRun = (id: number) => {
    if (window.confirm(`Excluir a execução #${id}? As vagas encontradas são mantidas.`)) remove.mutate(id);
  };
  return (
    <div className="space-y-4">
      {scanners.data && scanners.data.length > 0 && <ScannersTable scanners={scanners.data} />}
      <DocumentationPanel />
      {config.data && <ConfigView config={config.data} />}
      {runs.isError && <ErrorBox message="Não foi possível carregar as execuções. Verifique se a API está rodando." />}
      {runs.isLoading && <p className="text-sm text-grafite-500">Carregando execuções…</p>}
      {runs.isSuccess && runs.data.length === 0 && <p className="text-sm text-grafite-500">Nenhuma execução ainda.</p>}
      {clear.error && <ErrorBox message={clear.error.message} />}
      {runs.data && (
        <RunsTable
          runs={runs.data}
          onSelect={setSelectedId}
          onDelete={deleteRun}
          disabled={remove.isPending}
          clearDisabled={clear.isPending || !runs.data.length}
          onClear={() => {
            if (window.confirm("Apagar o histórico de execuções? As vagas encontradas são mantidas.")) clear.mutate();
          }}
        />
      )}
      {selectedRun && <RunDetail run={selectedRun} onClose={closeDetail} />}
      {remove.error && <ErrorBox message={remove.error.message} />}
    </div>
  );
}
