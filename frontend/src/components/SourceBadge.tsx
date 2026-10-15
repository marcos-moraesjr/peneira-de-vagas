import { sourceLabel } from "../lib/failures";
import { sourceColors } from "./ui";

export function SourceBadge({ fonte }: { fonte: string }) {
  const color = sourceColors[fonte] ?? "bg-linha-2 text-grafite-700";
  return <span className={`rounded-selo px-2 py-0.5 text-[11px] font-semibold ${color}`}>{sourceLabel(fonte)}</span>;
}
