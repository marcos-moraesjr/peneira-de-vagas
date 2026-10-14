const SECONDS_PER_MINUTE = 60;
const MINUTES_PER_HOUR = 60;
const HOURS_PER_DAY = 24;

const relative = new Intl.RelativeTimeFormat("pt-BR", { numeric: "always" });
const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.floor((now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < SECONDS_PER_MINUTE) return "agora";
  const minutes = Math.floor(seconds / SECONDS_PER_MINUTE);
  if (minutes < MINUTES_PER_HOUR) return relative.format(-minutes, "minute");
  const hours = Math.floor(minutes / MINUTES_PER_HOUR);
  if (hours < HOURS_PER_DAY) return relative.format(-hours, "hour");
  return relative.format(-Math.floor(hours / HOURS_PER_DAY), "day");
}

export function formatDuration(start: string, end: string | null): string {
  if (!end) return "—";
  const seconds = Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000));
  if (seconds < SECONDS_PER_MINUTE) return `${seconds} s`;
  return `${Math.floor(seconds / SECONDS_PER_MINUTE)} min ${seconds % SECONDS_PER_MINUTE} s`;
}

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** AAAA-MM-DD → DD/MM/AAAA, sem passar por Date (evita deslocar o dia pelo fuso). */
export function formatDate(isoDate: string): string {
  return isoDate.split("-").reverse().join("/");
}
