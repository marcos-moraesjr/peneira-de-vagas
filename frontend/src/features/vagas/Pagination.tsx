import { buttonSecondary } from "../../components/ui";

type Props = { page: number; totalPages: number; onPage: (page: number) => void };

/** Páginas a mostrar: primeira, última e a atual com vizinhas; `null` marca uma lacuna ("…"). */
function visiblePages(page: number, totalPages: number): (number | null)[] {
  const wanted = new Set([1, totalPages, page - 1, page, page + 1]);
  const pages = [...wanted].filter((n) => n >= 1 && n <= totalPages).sort((a, b) => a - b);
  return pages.flatMap((n, i) => (i > 0 && n - pages[i - 1] > 1 ? [null, n] : [n]));
}

export function Pagination({ page, totalPages, onPage }: Props) {
  if (totalPages <= 1) return null;
  const item = "min-w-9 px-2.5 py-1.5 text-dado";
  return (
    <nav aria-label="Paginação" className="flex flex-wrap items-center gap-1.5">
      <button type="button" className={`${buttonSecondary} ${item}`} disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Anterior
      </button>
      {visiblePages(page, totalPages).map((n, i) =>
        n === null ? (
          <span key={`gap-${i}`} aria-hidden className="px-1 text-grafite-400">
            …
          </span>
        ) : (
          <button
            key={n}
            type="button"
            aria-label={`Página ${n}`}
            aria-current={n === page ? "page" : undefined}
            className={n === page ? `${item} rounded-botao border border-grafite-900 bg-grafite-900 font-medium text-painel` : `${buttonSecondary} ${item}`}
            onClick={() => onPage(n)}
          >
            {n}
          </button>
        ),
      )}
      <button type="button" className={`${buttonSecondary} ${item}`} disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
        Próxima
      </button>
    </nav>
  );
}
