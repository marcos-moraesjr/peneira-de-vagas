import { useEffect, useState } from "react";
import { buttonSecondary } from "./ui";

type Theme = "light" | "dark";
const STORAGE_KEY = "peneira-tema";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* armazenamento indisponível: segue o sistema */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Alterna o tema claro/escuro (`data-theme` no `<html>`) e lembra a escolha no navegador. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* sem persistência: vale só nesta sessão */
    }
  }
  return (
    <button type="button" className={`${buttonSecondary} flex items-center gap-2`} onClick={toggle}>
      <span aria-hidden>{theme === "dark" ? "☀" : "☾"}</span>
      {theme === "dark" ? "Tema claro" : "Tema escuro"}
    </button>
  );
}
