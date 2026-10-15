import { useState, type FormEvent } from "react";
import { useActivateConjunto, useAddConjunto, useConjuntos, useCopyConjunto, useDeleteConjunto, useRenameConjunto } from "../api/hooks";
import { buttonDanger, buttonSecondary, card, inputClass, label } from "./ui";

type EditState = { id: number; mode: "rename" | "copy"; name: string } | null;

export function ConjuntosPanel() {
  const conjuntos = useConjuntos();
  const activate = useActivateConjunto();
  const add = useAddConjunto();
  const remove = useDeleteConjunto();
  const rename = useRenameConjunto();
  const copy = useCopyConjunto();
  const [nome, setNome] = useState("");
  const [origem, setOrigem] = useState("");
  const [edicao, setEdicao] = useState<EditState>(null);
  const [error, setError] = useState<string | null>(null);
  const items = conjuntos.data ?? [];
  const fail = (failure: Error) => setError(failure.message);

  function create(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const onSuccess = () => {
      setNome("");
      setOrigem("");
    };
    if (origem) {
      copy.mutate({ id: Number(origem), nome }, { onSuccess, onError: fail });
      return;
    }
    add.mutate(nome, { onSuccess, onError: fail });
  }

  function startEdit(id: number, mode: "rename" | "copy") {
    const conjunto = items.find((item) => item.id === id);
    if (!conjunto) return;
    setError(null);
    setEdicao({ id, mode, name: mode === "copy" ? `${conjunto.nome} (cópia)` : conjunto.nome });
  }

  function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!edicao) return;
    setError(null);
    const action = edicao.mode === "copy" ? copy : rename;
    action.mutate({ id: edicao.id, nome: edicao.name }, { onSuccess: () => setEdicao(null), onError: fail });
  }

  function deleteConjunto(id: number, nomeConjunto: string) {
    if (items.length <= 1) return;
    if (!window.confirm(`Excluir o conjunto "${nomeConjunto}" com todas as suas palavras-chave, exclusões e vagas?`)) return;
    setError(null);
    remove.mutate(id, { onError: fail });
  }

  return (
    <section className={`${card} p-3!`} aria-label="Conjuntos de busca">
      <div className="mb-2">
        <h2 className="text-sm font-semibold text-grafite-900">Conjuntos de busca</h2>
        <p className="text-xs text-grafite-500">A busca usa só o conjunto ativo, com as palavras-chave (da busca e de ranking) e exclusões dele.</p>
      </div>
      <div className="overflow-x-auto rounded-botao border border-linha">
        <table className="w-full min-w-0 text-left" aria-label="Conjuntos de busca">
          <thead className="border-b border-linha bg-linha-2 text-rotulo uppercase text-grafite-500">
            <tr><th scope="col" className="w-28 px-3 py-1">Uso</th><th scope="col" className="px-3 py-1">Nome do conjunto</th><th scope="col" className="w-48 px-3 py-1">Ações</th></tr>
          </thead>
          <tbody className="divide-y divide-linha">
            {items.map((conjunto) => {
              const editing = edicao?.id === conjunto.id;
              return (
                <tr key={conjunto.id} className={conjunto.ativo ? "bg-linha-2/60" : undefined}>
                  <td className="px-3 py-0.5 align-middle">
                    <button type="button" onClick={() => { setError(null); activate.mutate(conjunto.id, { onError: fail }); }} disabled={conjunto.ativo} className={conjunto.ativo ? "inline-flex w-24 justify-center rounded-botao bg-grafite-900 px-2.5 py-0.5! text-xs font-semibold text-painel" : `${buttonSecondary} inline-flex w-24 justify-center px-2.5 py-0.5! text-xs`} aria-label={conjunto.ativo ? `${conjunto.nome} está ativo` : `Selecionar ${conjunto.nome}`}>
                      {conjunto.ativo ? "Ativo" : "Selecionar"}
                    </button>
                  </td>
                  <td className="px-3 py-0.5 text-dado text-grafite-900">
                    {editing ? (
                      <form onSubmit={submitEdit} className="flex gap-2">
                        <label className="sr-only" htmlFor={`nome-conjunto-${conjunto.id}`}>{edicao.mode === "copy" ? "Nome da cópia" : `Nome do conjunto ${conjunto.nome}`}</label>
                        <input id={`nome-conjunto-${conjunto.id}`} autoFocus value={edicao.name} onChange={(event) => setEdicao({ ...edicao, name: event.target.value })} className={`${inputClass} min-w-0 flex-1 py-1`} />
                        <button type="submit" className={`${buttonSecondary} px-2.5 py-0.5! text-xs`}>{edicao.mode === "copy" ? "Criar cópia" : "Salvar"}</button>
                        <button type="button" onClick={() => setEdicao(null)} className={`${buttonSecondary} px-2.5 py-0.5! text-xs`}>Cancelar</button>
                      </form>
                    ) : <button type="button" onClick={() => startEdit(conjunto.id, "rename")} className="font-semibold text-grafite-900 underline decoration-linha-2 underline-offset-4 hover:decoration-grafite-900" aria-label={`Editar ${conjunto.nome}`}>{conjunto.nome}</button>}
                  </td>
                  <td className="px-3 py-0.5">
                    {!editing && <button type="button" onClick={() => deleteConjunto(conjunto.id, conjunto.nome)} disabled={items.length <= 1} title={items.length <= 1 ? "É preciso manter pelo menos um conjunto" : undefined} className={`${buttonDanger} px-2.5 py-0.5! text-xs`} aria-label={`Excluir ${conjunto.nome}`}>Excluir</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <form onSubmit={create} className="mt-2 flex flex-wrap items-end gap-2 border-t border-linha pt-2">
        <div className="min-w-[220px] flex-1"><label htmlFor="novo-conjunto" className={`${label} mb-0.5 block`}>Novo conjunto</label><input id="novo-conjunto" placeholder="Ex.: Engenharia de dados" value={nome} onChange={(event) => setNome(event.target.value)} className={`${inputClass} w-full py-1!`} /></div>
        <div className="min-w-[220px]"><label htmlFor="copiar-palavras-de" className={`${label} mb-0.5 block`}>Copiar palavras de</label><select id="copiar-palavras-de" value={origem} onChange={(event) => setOrigem(event.target.value)} className={`${inputClass} w-full py-1!`}><option value="">Começar vazio</option>{items.map((conjunto) => <option key={conjunto.id} value={conjunto.id}>{conjunto.nome}</option>)}</select></div>
        <button type="submit" className={`${buttonSecondary} py-1!`}>Criar conjunto</button>
      </form>
      {error && <p role="alert" className="mt-3 text-sm text-erro-fg">{error}</p>}
    </section>
  );
}
