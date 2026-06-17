import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

/** Reads the theme that the no-FOUC inline script already applied to <html>. */
function getInitialTheme(): Theme {
  if (
    typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark")
  ) {
    return "dark";
  }
  return "light";
}

/**
 * Light/dark theme with persistence. The `.dark` class on <html> drives all
 * styling via CSS variable overrides; this hook keeps it in sync and stores
 * the choice so it survives reloads.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* storage unavailable — non-fatal */
    }
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#141310" : "#f7f4ee");
  }, [theme]);

  const toggle = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    [],
  );

  return { theme, toggle };
}
