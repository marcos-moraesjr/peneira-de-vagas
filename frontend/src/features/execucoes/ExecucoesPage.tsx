import { useState } from "react";
import { useConfig, useRuns, useScanners } from "../../api/hooks";
import type { Config, Run, Scanner } from "../../api/types";
import { ErrorBox } from "../../components/ErrorBox";
import { card } from "../../components/ui";
import { describeFailure, sourceLabel } from "../../lib/failures";
import { formatDate, formatDateTime, formatDuration } from "../../lib/format";

function SourcesTable({ run }: { run: Run }) {
  return (
    <table className="mt-2 w-full text-left text-sm">
      <thead>
        <tr className="text-xs uppercase text-slate-500">
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
          <tr key={source.fonte} className="border-t border-slate-100">
            <td className="py-1 font-medium">{sourceLabel(source.fonte)}</td>
            <td>
              {source.status === "falha"
                ? describeFailure(source.fonte, source.motivo ?? "erro_interno").message
                : source.status === "ok"
                  ? "ok"
                  : source.status}
            </td>
            <td className="text-right">{source.lidas}</td>
            <td className="text-right">{source.aprovadas}</td>
            <td className="text-right">{source.novas}</td>
            <td className="text-right">{source.scanner_versao ? `v${source.scanner_versao}` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RunItem({ run }: { run: Run }) {
  const [open, setOpen] = useState(false);
  const failed = run.fontes.filter((source) => source.status === "falha").length;
  return (
    <li className={card}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full flex-wrap items-center gap-x-4 text-left text-sm"
      >
        <span className="font-semibold">Execução #{run.id}</span>
        <span>{formatDateTime(run.inicio)}</span>
        <span className="text-slate-500">{formatDuration(run.inicio, run.fim)}</span>
        <span className={failed ? "text-amber-700" : "text-slate-500"}>
          {run.status === "executando" ? "em andamento" : failed ? `${failed} fonte(s) com falha` : "sem falhas"}
        </span>
      </button>
      {open && <SourcesTable run={run} />}
    </li>
  );
}

function ConfigView({ config }: { config: Config }) {
  const rows: [string, string][] = [
    ["Localidade", config.busca.localidade],
    ["Modalidade", config.busca.modalidade || "qualquer"],
    ["Janela da busca", `${config.busca.janela_horas} h`],
    ["Pontos por termo no título / na descrição", `${config.filtro.peso_titulo} / ${config.filtro.peso_descricao}`],
    ["Pontuação mínima", String(config.filtro.min_score)],
    ["Páginas de detalhe por execução", String(config.limites.max_paginas_detalhe)],
    ["Vagas lidas por fonte", String(config.limites.max_vagas_lista)],
    ["Pausa entre ações", `${config.ritmo.pausa_min_s}–${config.ritmo.pausa_max_s} s`],
  ];
  return (
    <section className={card}>
      <h2 className="mb-2 text-sm font-semibold text-slate-800">Configuração em vigor</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-slate-500">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        Para alterar, edite config.toml. Palavras-chave e exclusões são editadas na tela Vagas.
      </p>
    </section>
  );
}

const SCANNER_STATUS: Record<string, string> = { ok: "Em dia", atencao: "Atenção", refazer: "Refazer" };

function ScannersTable({ scanners }: { scanners: Scanner[] }) {
  return (
    <section className={card}>
      <h2 className="mb-2 text-sm font-semibold text-slate-800">Scanners (gerados pelo Claude)</h2>
      <table aria-label="Scanners" className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase text-slate-500">
            <th className="py-1">Fonte</th>
            <th>Versão</th>
            <th>Explorado em</th>
            <th>Gerado por</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {scanners.map((scanner) => (
            <tr key={scanner.fonte} className="border-t border-slate-100" title={scanner.mensagem}>
              <td className="py-1 font-medium">{sourceLabel(scanner.fonte)}</td>
              <td>v{scanner.versao}</td>
              <td>{formatDate(scanner.explorado_em)}</td>
              <td>{scanner.gerado_por}</td>
              <td className={scanner.status === "ok" ? "" : "font-medium text-amber-700"}>
                {SCANNER_STATUS[scanner.status] ?? scanner.status}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function ExecucoesPage() {
  const runs = useRuns();
  const config = useConfig();
  const scanners = useScanners();
  return (
    <div className="space-y-4">
      {scanners.data && scanners.data.length > 0 && <ScannersTable scanners={scanners.data} />}
      {runs.isError && <ErrorBox message="Não foi possível carregar as execuções. Verifique se a API está rodando." />}
      {runs.isLoading && <p className="text-sm text-slate-500">Carregando execuções…</p>}
      {runs.isSuccess && runs.data.length === 0 && <p className="text-sm text-slate-500">Nenhuma execução ainda.</p>}
      <ul className="space-y-2">
        {runs.data?.map((run) => <RunItem key={run.id} run={run} />)}
      </ul>
      {config.data && <ConfigView config={config.data} />}
    </div>
  );
}
