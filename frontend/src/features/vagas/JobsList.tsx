import type { Job } from "../../api/types";
import { SourceBadge } from "../../components/SourceBadge";
import { buttonSecondary } from "../../components/ui";
import { formatDay, timeAgo } from "../../lib/format";

export type SortColumn = "titulo" | "empresa" | "localidade" | "publicada_em" | "encontrada_em" | "fonte" | "pontos";
export type Sort = { column: SortColumn; direction: "asc" | "desc" } | null;

type Props = {
  jobs: Job[];
  onSeen: (job: Job, visto: boolean) => void;
  sort: Sort;
  onSort: (column: SortColumn) => void;
};

const COLUMNS: { label: string; column: SortColumn }[] = [
  { label: "Vaga", column: "titulo" },
  { label: "Empresa", column: "empresa" },
  { label: "Localidade", column: "localidade" },
  { label: "Publicada", column: "publicada_em" },
  { label: "Encontrada", column: "encontrada_em" },
  { label: "Plataforma", column: "fonte" },
  { label: "Pontos", column: "pontos" },
];
const cell = "px-3 py-2 align-middle";

export function JobsList({ jobs, onSeen, sort, onSort }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {COLUMNS.map(({ label, column }) => {
              const active = sort?.column === column;
              return (
                <th
                  key={column}
                  scope="col"
                  aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
                  className="px-3 py-2 font-medium"
                >
                  <button type="button" onClick={() => onSort(column)} className="flex items-center gap-1 uppercase hover:text-slate-900">
                    {label}
                    <span aria-hidden className={active ? "text-slate-900" : "text-slate-300"}>
                      {active ? (sort.direction === "asc" ? "▲" : "▼") : "↕"}
                    </span>
                  </button>
                </th>
              );
            })}
            <th scope="col" className="px-3 py-2 font-medium">
              Ações
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {jobs.map((job) => (
            <tr key={job.id} className={job.visto ? "text-slate-500" : ""}>
              <td className={`${cell} max-w-sm`}>
                <div className="flex items-center gap-2">
                  {job.visto ? (
                    <span className="w-2 shrink-0" />
                  ) : (
                    <span role="img" aria-label="Vaga nova" className="h-2 w-2 shrink-0 rounded-full bg-sky-600" />
                  )}
                  <a
                    href={job.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => !job.visto && onSeen(job, true)}
                    className={`truncate hover:underline ${job.visto ? "" : "font-semibold text-slate-900"}`}
                  >
                    {job.titulo}
                  </a>
                </div>
              </td>
              <td className={cell}>{job.empresa || "—"}</td>
              <td className={cell}>{job.localidade || "—"}</td>
              <td className={`${cell} whitespace-nowrap`}>{job.publicada_em ? formatDay(job.publicada_em) : "—"}</td>
              <td className={`${cell} whitespace-nowrap`}>{timeAgo(job.encontrada_em)}</td>
              <td className={cell}>
                <SourceBadge fonte={job.fonte} />
              </td>
              <td className={cell}>{job.pontos}</td>
              <td className={cell}>
                <button type="button" className={`${buttonSecondary} whitespace-nowrap`} onClick={() => onSeen(job, !job.visto)}>
                  {job.visto ? "Marcar como nova" : "Marcar como vista"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
