import { useRef, useState, type FormEvent } from "react";
import { useAddKeyword, useDeleteKeyword, useKeywords } from "../api/hooks";
import type { KeywordType } from "../api/types";
import { buttonDark, buttonSecondary, card, inputClass } from "./ui";

const TEXTS: Record<KeywordType, { titulo: string; campo: string; vazio: string; dica: string }> = {
  busca: {
    titulo: "Palavras-chave da busca",
    campo: "Nova palavra-chave",
    vazio: "Nenhuma palavra-chave. Adicione ao menos uma palavra-chave para buscar.",
    dica: "Cada palavra vira uma busca em cada plataforma. Vale a partir da próxima busca.",
  },
  ranking: {
    titulo: "Palavras-chave de ranking",
    campo: "Nova palavra de ranking",
    vazio: "Nenhuma palavra de ranking.",
    dica: "Não fazem busca: só pontuam as vagas encontradas (junto com as palavras da busca).",
  },
  exclusao: {
    titulo: "Exclusões",
    campo: "Nova exclusão",
    vazio: "Nenhuma exclusão.",
    dica: "Vagas com esses termos são descartadas.",
  },
};

const CHIP_COLORS: Record<KeywordType, string> = {
  busca: "border-sinal/40 bg-sinal-bg text-sinal-fg",
  ranking: "border-atencao/50 bg-atencao-bg text-atencao-fg",
  exclusao: "border-erro/40 bg-erro-bg text-erro-fg",
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
      <h2 className="mb-3 text-base font-semibold text-grafite-900">{titulo ?? texts.titulo}</h2>
      <form onSubmit={submit} className="flex gap-2">
        <input
          ref={input}
          aria-label={texts.campo}
          value={termo}
          onChange={(event) => setTermo(event.target.value)}
          className={`${inputClass} min-w-0 flex-1`}
        />
        <button type="submit" className={tipo === "exclusao" ? buttonSecondary : buttonDark}>
          Adicionar
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-2 text-sm text-erro-fg">
          {error}
        </p>
      )}
      {keywords.data?.length === 0 && <p className="mt-2 text-sm text-grafite-500">{texts.vazio}</p>}
      <ul className="mt-2 flex flex-wrap gap-2">
        {keywords.data?.map((keyword) => (
          <li key={keyword.id} className={`flex items-center gap-2 rounded-selo border py-1 pl-2.5 pr-1.5 text-dado ${CHIP_COLORS[tipo]}`}>
            <span>{keyword.termo}</span>
            <button
              type="button"
              aria-label={`Remover ${keyword.termo}`}
              onClick={() => remove.mutate(keyword.id)}
              className="rounded-full px-1 text-current opacity-60 no-underline hover:opacity-100"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-grafite-500">{texts.dica}</p>
    </section>
  );
}
