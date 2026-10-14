import type { Job } from "../../api/types";
import { SourceBadge } from "../../components/SourceBadge";
import { buttonSecondary } from "../../components/ui";
import { timeAgo } from "../../lib/format";

type Props = { jobs: Job[]; onSeen: (job: Job, visto: boolean) => void };

export function JobsList({ jobs, onSeen }: Props) {
  return (
    <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
      {jobs.map((job) => (
        <li key={job.id} className={`flex items-center gap-3 px-4 py-3 ${job.visto ? "text-slate-500" : ""}`}>
          {job.visto ? (
            <span className="w-2" />
          ) : (
            <span role="img" aria-label="Vaga nova" className="h-2 w-2 shrink-0 rounded-full bg-sky-600" />
          )}
          <div className="min-w-0 flex-1">
            <a
              href={job.link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => !job.visto && onSeen(job, true)}
              className={`block truncate text-sm hover:underline ${job.visto ? "" : "font-semibold text-slate-900"}`}
            >
              {job.titulo}
            </a>
            <p className="truncate text-xs text-slate-500">
              {job.empresa || "Empresa não informada"} · encontrada {timeAgo(job.encontrada_em)} · {job.pontos} pts
            </p>
          </div>
          <SourceBadge fonte={job.fonte} />
          <button type="button" className={buttonSecondary} onClick={() => onSeen(job, !job.visto)}>
            {job.visto ? "Marcar como nova" : "Marcar como vista"}
          </button>
        </li>
      ))}
    </ul>
  );
}
