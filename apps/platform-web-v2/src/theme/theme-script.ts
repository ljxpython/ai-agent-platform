import { DEFAULT_THEME, THEME_STORAGE_KEY, type PlatformThemeId } from "./theme-config";

const THEME_CLASS_PREFIX = "theme-";

export function getThemeClassName(theme: PlatformThemeId): string {
  return `${THEME_CLASS_PREFIX}${theme}`;
}

export function buildThemeInitScript(): string {
  return `
    (function() {
      var storageKey = ${JSON.stringify(THEME_STORAGE_KEY)};
      var defaultTheme = ${JSON.stringify(DEFAULT_THEME)};
      var root = document.documentElement;
      var savedTheme = window.localStorage.getItem(storageKey) || defaultTheme;
      root.dataset.theme = savedTheme;
      root.classList.add(${JSON.stringify(THEME_CLASS_PREFIX)} + savedTheme);
    })();
  `;
}
