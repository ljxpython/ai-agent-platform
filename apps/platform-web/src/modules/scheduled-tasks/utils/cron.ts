/**
 * Cron 表达式预设与解析纯函数工具（移植并精炼自 DeerFlow）
 * 仅用于标准 5 字段 cron: 分 时 日 月 周
 */

export type CronPreset = "hourly" | "daily" | "weekly" | "monthly" | "custom";
export type Weekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

export interface CronParts {
  minute?: number;
  hour?: number;
  weekdays?: Weekday[];
  dayOfMonth?: number;
  raw?: string;
}

export const WEEKDAYS: Weekday[] = [
  "mon",
  "tue",
  "wed",
  "thu",
  "fri",
  "sat",
  "sun",
];

export const ZH_WEEKDAY: Record<Weekday, string> = {
  mon: "周一",
  tue: "周二",
  wed: "周三",
  thu: "周四",
  fri: "周五",
  sat: "周六",
  sun: "周日",
};

const WEEKDAY_TO_CRON: Record<Weekday, string> = {
  mon: "1",
  tue: "2",
  wed: "3",
  thu: "4",
  fri: "5",
  sat: "6",
  sun: "0",
};

const CRON_TO_WEEKDAY: Record<string, Weekday> = {
  "0": "sun",
  "1": "mon",
  "2": "tue",
  "3": "wed",
  "4": "thu",
  "5": "fri",
  "6": "sat",
  "7": "sun",
};

function clamp(
  value: number | undefined,
  min: number,
  max: number,
  fallback: number,
): number {
  const n =
    typeof value === "number" && Number.isFinite(value) ? value : fallback;
  return Math.max(min, Math.min(max, Math.trunc(n)));
}

export function pad2(n: number): string {
  return String(Math.trunc(Number.isFinite(n) ? n : 0)).padStart(2, "0");
}

function orderedWeekdays(days: Weekday[] | undefined): Weekday[] {
  const set = new Set(days ?? []);
  return WEEKDAYS.filter((w) => set.has(w));
}

/**
 * 将预设和字段组装成 5 字段 Cron 表达式
 */
export function serializeCron(preset: CronPreset, parts: CronParts): string {
  const m = clamp(parts.minute, 0, 59, 0);
  const h = clamp(parts.hour, 0, 23, 9);
  switch (preset) {
    case "hourly":
      return `${m} * * * *`;
    case "daily":
      return `${m} ${h} * * *`;
    case "weekly": {
      const ordered = orderedWeekdays(parts.weekdays);
      if (ordered.length === 0) {
        return `${m} ${h} * * *`;
      }
      const dow = ordered.map((w) => WEEKDAY_TO_CRON[w]).join(",");
      return `${m} ${h} * * ${dow}`;
    }
    case "monthly": {
      const dom = clamp(parts.dayOfMonth, 1, 31, 1);
      return `${m} ${h} ${dom} * *`;
    }
    case "custom":
      return (parts.raw ?? "").trim() || "0 9 * * *";
  }
}

function isStar(field: string): boolean {
  return field === "*";
}

function isSimpleDowList(field: string): boolean {
  return field.split(",").every((tok) => /^[0-7]$/.test(tok));
}

/**
 * 反解析 Cron 表达式为预设类型及相应字段，无法标准解析的归为 custom
 */
export function parseCron(cron: string): {
  preset: CronPreset;
  parts: CronParts;
} {
  const expr = cron.trim();
  const fields = expr.split(/\s+/);
  if (fields.length !== 5) {
    return { preset: "custom", parts: { raw: expr } };
  }

  const mF = fields[0]!;
  const hF = fields[1]!;
  const domF = fields[2]!;
  const monF = fields[3]!;
  const dowF = fields[4]!;
  const numMinute = /^\d+$/.test(mF);
  const numHour = /^\d+$/.test(hF);
  const numDom = /^\d+$/.test(domF);
  const stars = isStar(domF) && isStar(monF);

  // hourly: "M * * * *"
  if (numMinute && isStar(hF) && stars && isStar(dowF)) {
    return {
      preset: "hourly",
      parts: { minute: Number(mF) },
    };
  }

  // daily: "M H * * *"
  if (numMinute && numHour && stars && isStar(dowF)) {
    return {
      preset: "daily",
      parts: { minute: Number(mF), hour: Number(hF) },
    };
  }

  // weekly: "M H * * DOW[,DOW...]"
  if (numMinute && numHour && stars && isSimpleDowList(dowF)) {
    const rawTokens = dowF.split(",");
    const days: Weekday[] = [];
    for (const tok of rawTokens) {
      const w = CRON_TO_WEEKDAY[tok];
      if (w && !days.includes(w)) {
        days.push(w);
      }
    }
    return {
      preset: "weekly",
      parts: {
        minute: Number(mF),
        hour: Number(hF),
        weekdays: orderedWeekdays(days),
      },
    };
  }

  // monthly: "M H DOM * *"
  if (numMinute && numHour && numDom && isStar(monF) && isStar(dowF)) {
    return {
      preset: "monthly",
      parts: {
        minute: Number(mF),
        hour: Number(hF),
        dayOfMonth: Number(domF),
      },
    };
  }

  return { preset: "custom", parts: { raw: expr } };
}

/**
 * 生成人类友好的描述文本
 */
export function describeCron(cron: string): string {
  if (!cron || !cron.trim()) return "—";
  const { preset, parts } = parseCron(cron);
  const m = pad2(parts.minute ?? 0);
  const h = pad2(parts.hour ?? 0);

  switch (preset) {
    case "hourly":
      return `每小时第 ${parts.minute ?? 0} 分钟`;
    case "daily":
      return `每天 ${h}:${m}`;
    case "weekly": {
      const days = (parts.weekdays ?? []).map((w) => ZH_WEEKDAY[w]).join("、");
      return `每${days || "天"} ${h}:${m}`;
    }
    case "monthly":
      return `每月 ${parts.dayOfMonth ?? 1} 日 ${h}:${m}`;
    case "custom":
      return `自定义 (${cron})`;
  }
}
