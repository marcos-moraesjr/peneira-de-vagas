import { useRef, useState, type FormEvent } from "react";
import { useAddKeyword, useDeleteKeyword, useKeywords } from "../api/hooks";
import type { KeywordType } from "../api/types";
import { buttonSecondary, card, inputClass } from "./ui";

const TEXTS: Record<KeywordType, { titulo: string; campo: string; vazio: string; dica: string }> = {
  busca: {
    titulo: "Palavras-chave",
    campo: "Nova palavra-chave",
    vazio: "Nenhuma palavra-chave. Adicione ao menos uma palavra-chave para buscar.",
    dica: "Vale a partir da próxima busca.",
  },
  exclusao: {
    titulo: "Exclusões",
    campo: "Nova exclusão",
    vazio: "Nenhuma exclusão.",
    dica: "Vagas com esses termos são descartadas.",
  },
};

export function KeywordsPanel({ tipo, titulo }: { tipo: KeywordType; titulo?: string }) {
  const texts = TEXTS[tipo];
  const keywords = useKeywords(tipo);
  const add = useAddKeyword(tipo);
  const remove = useDeleteKeyword();
  const [termo, setTermo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    add.mutate(termo, {
      onSuccess: () => {
        setTermo("");
        input.current?.focus();
      },
      onError: (failure) => setError(failure.message),
    });
  }

  return (
    <section className={card} aria-label={titulo ?? texts.titulo}>
      <h2 className="mb-2 text-sm font-semibold text-slate-800">{titulo ?? texts.titulo}</h2>
      <form onSubmit={submit} className="flex gap-2">
        <input
          ref={input}
          aria-label={texts.campo}
          value={termo}
          onChange={(event) => setTermo(event.target.value)}
          className={`${inputClass} min-w-0 flex-1`}
        />
        <button type="submit" className={buttonSecondary}>
          Adicionar
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {keywords.data?.length === 0 && <p className="mt-2 text-sm text-slate-500">{texts.vazio}</p>}
      <ul className="mt-2 flex flex-wrap gap-2">
        {keywords.data?.map((keyword) => (
          <li key={keyword.id} className="flex items-center gap-1 rounded-full bg-slate-100 py-1 pl-3 pr-1 text-sm">
            <span>{keyword.termo}</span>
            <button
              type="button"
              aria-label={`Remover ${keyword.termo}`}
              onClick={() => remove.mutate(keyword.id)}
              className="rounded-full px-2 text-slate-500 hover:bg-slate-200 hover:text-slate-900"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">{texts.dica}</p>
    </section>
  );
}
