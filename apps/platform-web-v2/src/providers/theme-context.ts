import { createContext } from "react";

import { THEME_OPTIONS, type PlatformThemeId } from "@/theme/theme-config";

export type ThemeContextValue = {
  theme: PlatformThemeId;
  setTheme: (theme: PlatformThemeId) => void;
  options: typeof THEME_OPTIONS;
};

export const ThemeContext = createContext<ThemeContextValue | null>(null);
