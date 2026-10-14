import { sourceLabel } from "../lib/failures";
import { sourceColors } from "./ui";

export function SourceBadge({ fonte }: { fonte: string }) {
  const color = sourceColors[fonte] ?? "bg-slate-100 text-slate-700";
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${color}`}>{sourceLabel(fonte)}</span>;
}
