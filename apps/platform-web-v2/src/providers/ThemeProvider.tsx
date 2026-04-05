"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ThemeContext,
  type ThemeContextValue,
} from "@/providers/theme-context";
import {
  DEFAULT_THEME,
  THEME_OPTIONS,
  THEME_STORAGE_KEY,
  type PlatformThemeId,
} from "@/theme/theme-config";

function applyTheme(theme: PlatformThemeId) {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  for (const option of THEME_OPTIONS) {
    root.classList.remove(`theme-${option.id}`);
  }
  root.dataset.theme = theme;
  root.classList.add(`theme-${theme}`);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<PlatformThemeId>(DEFAULT_THEME);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const savedTheme = window.localStorage.getItem(
      THEME_STORAGE_KEY,
    ) as PlatformThemeId | null;
    const nextTheme =
      savedTheme && THEME_OPTIONS.some((option) => option.id === savedTheme)
        ? savedTheme
        : DEFAULT_THEME;
    setThemeState(nextTheme);
    applyTheme(nextTheme);
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme: (nextTheme) => {
        setThemeState(nextTheme);
        applyTheme(nextTheme);
        if (typeof window !== "undefined") {
          window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
        }
      },
      options: THEME_OPTIONS,
    }),
    [theme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}
