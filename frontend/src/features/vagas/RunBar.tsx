import { useState } from "react";
import type { Run } from "../../api/types";
import { buttonPrimary } from "../../components/ui";
import { sourceLabel } from "../../lib/failures";
import { timeAgo } from "../../lib/format";
import { ESTADOS_BRASILEIROS } from "../../lib/estados";
import { MODALIDADES } from "../../lib/format";

/** Plataformas que só buscam com o Chrome dedicado aberto (a Gupy usa a API e não precisa). */
const PRECISAM_DO_NAVEGADOR = ["linkedin", "indeed"];

const campo = "flex items-center gap-2 text-sm text-grafite-700";
const controle = "rounded-botao border border-linha bg-painel px-3 py-2 text-dado text-grafite-900";
const miniBotao = "rounded px-1 text-grafite-500 hover:bg-linha-2 hover:text-grafite-900 disabled:cursor-not-allowed disabled:opacity-30";

const STATUS_TEXT: Record<string, string> = {
  aguardando: "aguardando",
  buscando: "buscando",
  ok: "concluída",
  falha: "falhou",
};

const STATUS_CLASS: Record<string, string> = {
  aguardando: "text-atencao-fg",
  buscando: "text-atencao-fg",
  ok: "text-sinal-fg",
  falha: "text-erro-fg",
};

type EstadoConjunto = "sucesso" | "andamento" | "falha" | "pendente";

const ESTADO_CLASSE: Record<EstadoConjunto, string> = {
  sucesso: "border-sinal-ponto bg-sinal-bg text-sinal-fg",
  andamento: "border-atencao bg-atencao-bg text-atencao-fg",
  falha: "border-erro bg-erro-bg text-erro-fg",
  pendente: "border-linha bg-papel text-grafite-700",
};

const ESTADO_TITULO: Record<EstadoConjunto, string> = {
  sucesso: "Concluído",
  andamento: "Em andamento",
  falha: "Falhou",
  pendente: "Aguardando",
};

/** Estado de cada conjunto da sequência, a partir das execuções mais recentes (uma por conjunto, em ordem).
 * A última execução localiza o conjunto atual; as anteriores só valem se seguirem a ordem da sequência. */
function estadosDaSequencia(nomes: string[], runs: Run[]): EstadoConjunto[] {
  const estados = nomes.map((): EstadoConjunto => "pendente");
  const atual = runs.length ? nomes.indexOf(runs[0].conjunto) : -1;
  for (let k = 0; atual >= 0 && k <= atual; k++) {
    const run = runs[k];
    if (!run || run.conjunto !== nomes[atual - k]) break;
    estados[atual - k] = run.status === "executando" ? "andamento" : run.fontes.some((fonte) => fonte.status === "falha") ? "falha" : "sucesso";
  }
  return estados;
}

function newJobsText(run: Run): string {
  const total = run.fontes.reduce((sum, source) => sum + source.novas, 0);
  return `${total} ${total === 1 ? "vaga nova" : "vagas novas"}`;
}

type Props = {
  latest: Run | undefined;
  /** Execuções, da mais recente para a mais antiga; colorem a sequência de conjuntos. */
  runs: Run[];
  canSearch: boolean;
  /** Chrome dedicado aberto; `undefined` enquanto não se sabe (não bloqueia). */
  navegadorAberto?: boolean;
  starting: boolean;
  sources: string[];
  /** `null` = todas as plataformas. */
  onSearch: (sources: string[] | null) => void;
  estado: string;
  onEstadoChange: (estado: string) => void;
  modalidade: string;
  onModalidadeChange: (modalidade: string) => void;
  janelaDias: string;
  onJanelaDiasChange: (dias: string) => void;
  conjuntos: { id: number; nome: string; ativo: boolean }[];
  /** Ids dos conjuntos a buscar, em ordem; vazia = só o conjunto ativo. */
  sequencia: number[];
  onSequenciaChange: (ids: number[]) => void;
  hint?: string;
};

type RunStatusProps = {
  latest: Run | undefined;
  runs: Run[];
  /** Nomes dos conjuntos da sequência, em ordem; vazia = só o conjunto ativo. */
  sequencia: string[];
};

export function RunStatus({ latest, runs, sequencia }: RunStatusProps) {
  if (latest?.status !== "executando") return null;
  const posicao = estadosDaSequencia(sequencia, runs).indexOf("andamento");
  const conjunto = posicao >= 0 ? sequencia[posicao] : latest.conjunto;
  return (
    <div className="flex flex-wrap items-center gap-3">
      {conjunto && (
        <span className="rounded-botao bg-atencao-bg px-2 py-1 text-[13px] font-semibold text-atencao-fg">
          {posicao >= 0 && sequencia.length > 1 ? `Buscando agora: ${conjunto} (${posicao + 1} de ${sequencia.length})` : `Buscando agora: ${conjunto}`}
        </span>
      )}
      <ul role="status" className="flex flex-wrap items-center gap-3 text-[13px] font-semibold text-grafite-500">
        {latest.fontes.map((source) => (
          <li key={source.fonte} className={`flex items-center gap-2 border-l border-linha pl-3 ${STATUS_CLASS[source.status] ?? "text-grafite-500"}`}>
            <span aria-hidden className="h-2 w-2 rounded-full bg-current" />
            {sourceLabel(source.fonte)}: {STATUS_TEXT[source.status] ?? source.status}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RunBar({
  latest,
  runs,
  canSearch,
  navegadorAberto,
  starting,
  sources,
  onSearch,
  estado,
  onEstadoChange,
  modalidade,
  onModalidadeChange,
  janelaDias,
  onJanelaDiasChange,
  conjuntos,
  sequencia,
  onSequenciaChange,
  hint,
}: Props) {
  const [selected, setSelected] = useState<string[]>(sources);
  const chosen = sources.filter((name) => selected.includes(name));
  const running = latest?.status === "executando";
  const bloqueadoPeloNavegador = navegadorAberto === false && chosen.some((name) => PRECISAM_DO_NAVEGADOR.includes(name));

  function move(index: number, delta: number) {
    const next = [...sequencia];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    onSequenciaChange(next);
  }
  const [arrastando, setArrastando] = useState<number | null>(null);
  function soltarEm(destino: number) {
    const origem = arrastando === null ? -1 : sequencia.indexOf(arrastando);
    setArrastando(null);
    if (origem < 0 || origem === destino) return;
    const next = [...sequencia];
    const [item] = next.splice(origem, 1);
    next.splice(destino, 0, item);
    onSequenciaChange(next);
  }
  const fora = conjuntos.filter((item) => !sequencia.includes(item.id));
  const nomes = sequencia.map((id) => conjuntos.find((item) => item.id === id)?.nome ?? String(id));
  const estados = estadosDaSequencia(nomes, runs);

  function toggle(name: string) {
    setSelected((current) => (current.includes(name) ? current.filter((item) => item !== name) : [...current, name]));
  }
  return (
    <div role="region" aria-label="Controles da busca" className="flex flex-col gap-4 rounded-painel border border-linha bg-painel px-4 py-3 ">
      <div className="min-w-0 flex-1 space-y-3">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <h2 className="text-sm font-semibold text-grafite-900">Buscar nas plataformas</h2>
          <p className="text-xs text-grafite-500">Define o que será coletado nos sites; a janela de recência vale só para esta busca.</p>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <button
            type="button"
            className={buttonPrimary}
            disabled={!canSearch || running || starting || chosen.length === 0 || bloqueadoPeloNavegador}
            onClick={() => onSearch(chosen.length === sources.length ? null : chosen)}
          >
            {running ? "Buscando…" : "Buscar agora"}
          </button>
          <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-grafite-700" disabled={running}>
            <legend className="sr-only">Plataformas da busca</legend>
            {sources.map((name) => (
              <label key={name} className="flex items-center gap-2">
                <input type="checkbox" checked={selected.includes(name)} onChange={() => toggle(name)} />
                {sourceLabel(name)}
              </label>
            ))}
          </fieldset>
          <label className={campo}>
            Estado
            <select aria-label="Estado da busca" value={estado} onChange={(event) => onEstadoChange(event.target.value)} className={controle}>
              <option value="">Todos os estados</option>
              {ESTADOS_BRASILEIROS.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className={campo}>
            Modalidade
            <select aria-label="Modalidade da busca" value={modalidade} onChange={(event) => onModalidadeChange(event.target.value)} className={controle}>
              <option value="">Todas</option>
              {MODALIDADES.map((item) => <option key={item.valor} value={item.valor}>{item.rotulo}</option>)}
            </select>
          </label>
          <label className={campo}>
            Janela de recência (dias)
            <input
              aria-label="Janela de recência (dias)"
              type="number"
              min={1}
              value={janelaDias}
              onChange={(event) => onJanelaDiasChange(event.target.value)}
              className={`${controle} w-20`}
            />
          </label>
          {latest?.status === "concluida" && (
            <span className="text-legenda text-grafite-500">
              Última busca {timeAgo(latest.fim ?? latest.inicio)}:{" "}
              {newJobsText(latest)}
            </span>
          )}
          {hint && <span className="text-sm text-atencao-fg">{hint}</span>}
          {bloqueadoPeloNavegador && (
            <span className="text-sm text-atencao-fg">Abra o Chrome dedicado para buscar no LinkedIn ou no Indeed, ou desmarque os dois.</span>
          )}
        </div>
      </div>
      {conjuntos.length > 1 && (
        <section aria-label="Sequência de conjuntos" className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-linha pt-3 text-sm text-grafite-700">
          <div className="flex shrink-0 items-center gap-2">
            <h3 className="text-sm font-semibold text-grafite-900">Sequência de conjuntos</h3>
            <select
              aria-label="Adicionar à sequência"
              value=""
              disabled={running || fora.length === 0}
              onChange={(event) => event.target.value && onSequenciaChange([...sequencia, Number(event.target.value)])}
              className="w-28 rounded-botao border border-linha bg-painel px-2 py-1 text-dado text-grafite-900"
            >
              <option value="">Adicionar…</option>
              {fora.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}
            </select>
          </div>
          {sequencia.length === 0 ? (
            <p className="text-legenda text-grafite-500">Vazia: busca só o conjunto ativo.</p>
          ) : (
            <ol className="flex min-w-0 flex-1 gap-2 overflow-x-auto pb-1">
              {sequencia.map((id, index) => {
                const nome = nomes[index];
                const estado = estados[index];
                return (
                  <li
                    key={id}
                    data-estado={estado}
                    title={ESTADO_TITULO[estado]}
                    draggable={!running}
                    onDragStart={(event) => {
                      event.dataTransfer?.setData("text/plain", String(id));
                      setArrastando(id);
                    }}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      soltarEm(index);
                    }}
                    onDragEnd={() => setArrastando(null)}
                    className={`flex shrink-0 items-center gap-1.5 rounded-botao border px-2 py-1 ${ESTADO_CLASSE[estado]} ${running ? "" : "cursor-grab"} ${arrastando === id ? "opacity-50" : ""}`}
                  >
                    <span className="text-legenda opacity-70">{index + 1}.</span>
                    <span className="whitespace-nowrap" title={nome}>{nome}</span>
                    <button type="button" className={miniBotao} aria-label={`Subir ${nome}`} disabled={running || index === 0} onClick={() => move(index, -1)}>←</button>
                    <button type="button" className={miniBotao} aria-label={`Descer ${nome}`} disabled={running || index === sequencia.length - 1} onClick={() => move(index, 1)}>→</button>
                    <button type="button" className={`${miniBotao} hover:text-erro-fg`} aria-label={`Remover ${nome}`} disabled={running} onClick={() => onSequenciaChange(sequencia.filter((item) => item !== id))}>✕</button>
                  </li>
                );
              })}
            </ol>
          )}
        </section>
      )}
    </div>
  );
}
