"use client";

import { Palette } from "lucide-react";

import { useThemeContext } from "@/providers/useThemeContext";

export function ThemeToggle() {
  const { theme, setTheme, options } = useThemeContext();

  return (
    <label className="theme-toggle">
      <span className="theme-toggle__label">
        <Palette className="theme-toggle__icon" />
        Theme
      </span>
      <select
        aria-label="Theme selector"
        className="theme-toggle__select"
        value={theme}
        onChange={(event) => setTheme(event.target.value as typeof theme)}
      >
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
