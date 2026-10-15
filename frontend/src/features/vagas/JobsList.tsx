import type { Job } from "../../api/types";
import { SourceBadge } from "../../components/SourceBadge";
import { formatDay, modalidadeLabel, timeAgo } from "../../lib/format";

export type SortColumn = "titulo" | "empresa" | "palavra_chave" | "cidade" | "estado" | "modalidade" | "publicada_em" | "encontrada_em" | "fonte" | "pontos";
export type Sort = { column: SortColumn; direction: "asc" | "desc" } | null;

type Props = {
  jobs: Job[];
  onSeen: (job: Job, visto: boolean) => void;
  sort: Sort;
  onSort: (column: SortColumn) => void;
};

// `width`: largura da coluna na tabela de layout fixo (soma 100%), para a tabela caber sem rolagem lateral.
const COLUMNS: { label: string; column: SortColumn; width: string }[] = [
  { label: "Vaga", column: "titulo", width: "w-[22%]" },
  { label: "Empresa", column: "empresa", width: "w-[13%]" },
  { label: "Palavra-chave", column: "palavra_chave", width: "w-[11%]" },
  { label: "Cidade", column: "cidade", width: "w-[9%]" },
  { label: "Estado", column: "estado", width: "w-[5%]" },
  { label: "Modalidade", column: "modalidade", width: "w-[9%]" },
  { label: "Publicada", column: "publicada_em", width: "w-[8%]" },
  { label: "Encontrada", column: "encontrada_em", width: "w-[9%]" },
  { label: "Plataforma", column: "fonte", width: "w-[8%]" },
  { label: "Pontos", column: "pontos", width: "w-[6%]" },
];
const MAX_POINTS = 10;
const cell = "px-3 py-2 align-middle break-words";

export function JobsList({ jobs, onSeen, sort, onSort }: Props) {
  return (
    <div className="max-h-[65vh] overflow-y-auto rounded-painel border border-linha bg-painel">
      <table className="w-full table-fixed text-left text-sm">
        <thead className="sticky top-0 z-10 border-b border-linha bg-linha-2 text-rotulo uppercase text-grafite-700">
          <tr>
            {COLUMNS.map(({ label, column, width }) => {
              const active = sort?.column === column;
              return (
                <th
                  key={column}
                  scope="col"
                  aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
                  className={`px-3 py-3 font-semibold ${width}`}
                >
                  <button type="button" onClick={() => onSort(column)} className="flex items-center gap-1 uppercase hover:text-grafite-900">
                    {label}
                    <span aria-hidden className={active ? "text-grafite-900" : "text-linha"}>
                      {active ? (sort.direction === "asc" ? "▲" : "▼") : "↕"}
                    </span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-linha-2">
          {jobs.map((job) => (
            <tr key={job.id} className={`text-[13px] ${job.visto ? "text-grafite-500" : "bg-sinal-ponto/10 text-grafite-700"}`}>
              <td className={cell}>
                <div className="flex items-center gap-2">
                  {!job.visto && (
                    <span role="img" aria-label="Vaga nova" className="h-2 w-2 shrink-0 rounded-full bg-sinal-ponto" />
                  )}
                  <a
                    href={job.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => !job.visto && onSeen(job, true)}
                    className={`line-clamp-2 hover:underline ${job.visto ? "" : "font-semibold text-grafite-900"}`}
                  >
                    {job.titulo}
                  </a>
                </div>
              </td>
              <td className={cell}>{job.empresa || "—"}</td>
              <td className={cell}>{job.palavra_chave || "—"}</td>
              <td className={cell}>{job.cidade || "—"}</td>
              <td className={cell}>{job.estado || "—"}</td>
              <td className={cell}>{modalidadeLabel(job.modalidade) || "—"}</td>
              <td className={`${cell} whitespace-nowrap text-legenda`}>{job.publicada_em ? formatDay(job.publicada_em) : "—"}</td>
              <td className={`${cell} whitespace-nowrap text-legenda`}>{timeAgo(job.encontrada_em)}</td>
              <td className={cell}>
                <SourceBadge fonte={job.fonte} />
              </td>
              <td className={cell}>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 rounded-sm bg-linha-2">
                    <div className={`h-1.5 rounded-sm ${job.pontos >= 7 ? "bg-barra-alta" : "bg-barra-baixa"}`} style={{ width: `${Math.min(100, (job.pontos / MAX_POINTS) * 100)}%` }} />
                  </div>
                  <span className="w-4 text-right text-dado text-grafite-900">{job.pontos}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
