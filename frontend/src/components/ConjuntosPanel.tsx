import { useState, type FormEvent } from "react";
import { useActivateConjunto, useAddConjunto, useConjuntos, useCopyConjunto, useDeleteConjunto, useRenameConjunto } from "../api/hooks";
import { buttonSecondary, card, inputClass, label } from "./ui";

export function ConjuntosPanel() {
  const conjuntos = useConjuntos();
  const activate = useActivateConjunto();
  const add = useAddConjunto();
  const remove = useDeleteConjunto();
  const rename = useRenameConjunto();
  const copy = useCopyConjunto();
  const [nome, setNome] = useState("");
  const [edicao, setEdicao] = useState<{ modo: "renomear" | "copiar"; nome: string } | null>(null); // não nulo = editando o nome do conjunto ativo
  const [error, setError] = useState<string | null>(null);

  const items = conjuntos.data ?? [];
  const active = items.find((conjunto) => conjunto.ativo);
  const fail = (failure: Error) => setError(failure.message);

  function create(event: FormEvent) {
    event.preventDefault();
    setError(null);
    add.mutate(nome, { onSuccess: () => setNome(""), onError: fail });
  }

  function startEdit(modo: "renomear" | "copiar") {
    if (!active) return;
    setError(null);
    setEdicao({ modo, nome: modo === "copiar" ? `${active.nome} (cópia)` : active.nome });
  }

  function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!active || !edicao) return;
    setError(null);
    const action = edicao.modo === "copiar" ? copy : rename;
    action.mutate({ id: active.id, nome: edicao.nome }, { onSuccess: () => setEdicao(null), onError: fail });
  }

  function deleteActive() {
    if (!active) return;
    if (window.confirm(`Excluir o conjunto "${active.nome}" com todas as suas palavras-chave, exclusões e vagas?`)) {
      setError(null);
      remove.mutate(active.id, { onError: fail });
    }
  }

  return (
    <section className={card} aria-label="Conjuntos de busca">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-grafite-900">Conjuntos de busca</h2>
        <p className="text-xs text-grafite-500">A busca usa só o conjunto ativo, com as palavras-chave (da busca e de ranking) e exclusões dele.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 md:gap-0 md:divide-x md:divide-linha">
        <div className="md:pr-4">
          {edicao === null ? (
            <>
              <label htmlFor="conjunto-ativo" className={`${label} mb-1 block`}>
                Conjunto ativo
              </label>
              <div className="flex flex-wrap gap-2">
                <select
                  id="conjunto-ativo"
                  value={active?.id ?? ""}
                  onChange={(event) => {
                    setError(null);
                    activate.mutate(Number(event.target.value), { onError: fail });
                  }}
                  className={`${inputClass} min-w-0 flex-1`}
                >
                  {items.map((conjunto) => (
                    <option key={conjunto.id} value={conjunto.id}>
                      {conjunto.nome}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={() => startEdit("renomear")} disabled={!active} className={buttonSecondary}>
                  Renomear conjunto
                </button>
                <button type="button" onClick={() => startEdit("copiar")} disabled={!active} className={buttonSecondary}>
                  Copiar conjunto
                </button>
                <button
                  type="button"
                  onClick={deleteActive}
                  disabled={items.length <= 1}
                  title={items.length <= 1 ? "É preciso manter pelo menos um conjunto" : undefined}
                  className={`${buttonSecondary} text-erro-fg`}
                >
                  Excluir conjunto
                </button>
              </div>
            </>
          ) : (
            <form onSubmit={submitEdit}>
              <label htmlFor="novo-nome-conjunto" className={`${label} mb-1 block`}>
                {edicao.modo === "copiar" ? "Nome da cópia" : "Novo nome do conjunto"}
              </label>
              <div className="flex gap-2">
                <input
                  id="novo-nome-conjunto"
                  autoFocus
                  value={edicao.nome}
                  onChange={(event) => setEdicao({ ...edicao, nome: event.target.value })}
                  className={`${inputClass} min-w-0 flex-1`}
                />
                <button type="submit" className={buttonSecondary}>
                  {edicao.modo === "copiar" ? "Criar cópia" : "Salvar"}
                </button>
                <button type="button" onClick={() => setEdicao(null)} className={buttonSecondary}>
                  Cancelar
                </button>
              </div>
            </form>
          )}
        </div>
        <form onSubmit={create} className="md:pl-4">
          <label htmlFor="novo-conjunto" className={`${label} mb-1 block`}>
            Novo conjunto
          </label>
          <div className="flex gap-2">
            <input
              id="novo-conjunto"
              placeholder="Ex.: Engenharia de dados"
              value={nome}
              onChange={(event) => setNome(event.target.value)}
              className={`${inputClass} min-w-0 flex-1`}
            />
            <button type="submit" className={buttonSecondary}>
              Criar
            </button>
          </div>
        </form>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-erro-fg">
          {error}
        </p>
      )}
    </section>
  );
}
