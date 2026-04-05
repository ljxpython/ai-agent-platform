export const THEME_OPTIONS = [
  {
    id: "refine-hr",
    label: "Refine HR 系",
    description: "默认主题，企业后台风格，浅天蓝点缀。",
  },
  {
    id: "workspace-neutral",
    label: "Workspace Neutral",
    description: "通用中性工作台风格。",
  },
  {
    id: "soft-admin",
    label: "Soft Admin",
    description: "更柔和的暖色后台风格。",
  },
] as const;

export type PlatformThemeId = (typeof THEME_OPTIONS)[number]["id"];

export const DEFAULT_THEME: PlatformThemeId = "refine-hr";

export const THEME_STORAGE_KEY = "platform-web-v2:theme";
