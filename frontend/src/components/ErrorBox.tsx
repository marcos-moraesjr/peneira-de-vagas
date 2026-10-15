export function ErrorBox({ message }: { message: string }) {
  return <p className="rounded-painel border border-erro bg-erro-bg px-3 py-2 text-sm text-erro-fg">{message}</p>;
}
