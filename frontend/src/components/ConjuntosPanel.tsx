import { useState, type FormEvent } from "react";
import { useActivateConjunto, useAddConjunto, useConjuntos, useDeleteConjunto } from "../api/hooks";
import { buttonSecondary, card, inputClass } from "./ui";

export function ConjuntosPanel() {
  const conjuntos = useConjuntos();
  const activate = useActivateConjunto();
  const add = useAddConjunto();
  const remove = useDeleteConjunto();
  const [nome, setNome] = useState("");
  const [error, setError] = useState<string | null>(null);

  const items = conjuntos.data ?? [];
  const active = items.find((conjunto) => conjunto.ativo);
  const fail = (failure: Error) => setError(failure.message);

  function create(event: FormEvent) {
    event.preventDefault();
    setError(null);
    add.mutate(nome, { onSuccess: () => setNome(""), onError: fail });
  }

  function deleteActive() {
    if (!active) return;
    if (window.confirm(`Excluir o conjunto "${active.nome}" com todas as suas palavras-chave e exclusões?`)) {
      setError(null);
      remove.mutate(active.id, { onError: fail });
    }
  }

  return (
    <section className={card} aria-label="Conjuntos de busca">
      <h2 className="mb-2 text-sm font-semibold text-grafite-900">Conjuntos de busca</h2>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Conjunto ativo"
          value={active?.id ?? ""}
          onChange={(event) => {
            setError(null);
            activate.mutate(Number(event.target.value), { onError: fail });
          }}
          className={`${inputClass} min-w-0 flex-1 md:flex-none md:w-64`}
        >
          {items.map((conjunto) => (
            <option key={conjunto.id} value={conjunto.id}>
              {conjunto.nome}
            </option>
          ))}
        </select>
        <button type="button" onClick={deleteActive} disabled={items.length <= 1} className={`${buttonSecondary} disabled:opacity-50`}>
          Excluir conjunto
        </button>
        <form onSubmit={create} className="flex min-w-0 flex-1 gap-2">
          <input
            aria-label="Novo conjunto"
            placeholder="Nome do novo conjunto"
            value={nome}
            onChange={(event) => setNome(event.target.value)}
            className={`${inputClass} min-w-0 flex-1`}
          />
          <button type="submit" className={buttonSecondary}>
            Criar
          </button>
        </form>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-erro-fg">
          {error}
        </p>
      )}
      <p className="mt-2 text-xs text-grafite-500">A busca usa só o conjunto ativo, com as palavras-chave e exclusões dele.</p>
    </section>
  );
}
