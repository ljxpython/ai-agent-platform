"use client";

import { useContext } from "react";

import {
  ThemeContext,
  type ThemeContextValue,
} from "@/providers/theme-context";

export function useThemeContext(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useThemeContext must be used within ThemeProvider");
  }
  return context;
}
