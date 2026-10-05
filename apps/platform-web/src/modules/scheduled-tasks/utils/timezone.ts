/**
 * 时区与本地壁钟时间换算工具
 */

export interface TimezoneOption {
  value: string;
  label: string;
  [key: string]: unknown;
}

export const COMMON_TIMEZONES: TimezoneOption[] = [
  { value: "Asia/Shanghai", label: "中国标准时间 (Asia/Shanghai, UTC+8)" },
  { value: "UTC", label: "世界协调时 (UTC)" },
  { value: "Asia/Tokyo", label: "日本标准时间 (Asia/Tokyo, UTC+9)" },
  { value: "Europe/London", label: "伦敦时间 (Europe/London)" },
  { value: "America/New_York", label: "美东时间 (America/New_York)" },
  { value: "America/Los_Angeles", label: "美西时间 (America/Los_Angeles)" },
];

/**
 * 获取指定 IANA 时区在某个 UTC 时间点下的偏移量字符串，如 "+08:00"、"-04:00"、"Z"
 */
export function getTimezoneOffsetString(
  timeZone: string,
  date = new Date(),
): string {
  try {
    const formatter = new Intl.DateTimeFormat("en-US", {
      timeZone,
      timeZoneName: "longOffset",
    });
    const parts = formatter.formatToParts(date);
    const tzPart = parts.find((p) => p.type === "timeZoneName");
    if (!tzPart || tzPart.value === "GMT") return "+00:00";
    // tzPart.value 类似 "GMT+08:00" 或 "GMT-04:00"
    return tzPart.value.replace("GMT", "");
  } catch {
    return "+08:00"; // fallback
  }
}

/**
 * 将壁钟时间字符串 (如 "2026-10-06T09:30" 或 "2026-10-06T09:30:00")
 * 结合指定的时区名称，转为带明确偏移的标准 ISO 8601 字符串 (如 "2026-10-06T09:30:00+08:00")
 */
export function formatZonedIsoString(
  wallDateTime: string,
  timeZone: string,
): string {
  if (!wallDateTime || !wallDateTime.trim()) return "";
  const cleaned = wallDateTime.trim();
  // 补齐秒数
  const withSeconds = cleaned.length === 16 ? `${cleaned}:00` : cleaned;

  // 使用当前时间的大致偏移作为初值
  const offset = getTimezoneOffsetString(timeZone, new Date());
  return `${withSeconds}${offset}`;
}

/**
 * 将 ISO 时间字符串转化为适用于 datetime-local 控件的壁钟字符串 "YYYY-MM-DDTHH:mm"
 */
export function toDateTimeLocalValue(
  isoString: string | null | undefined,
): string {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "";

  const pad = (n: number) => String(n).padStart(2, "0");
  const year = d.getFullYear();
  const month = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());

  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

/**
 * 格式化展示时间，如 "2026-10-06 09:30:00"
 */
export function formatDisplayTime(
  isoString: string | null | undefined,
  timeZone = "Asia/Shanghai",
): string {
  if (!isoString) return "—";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return String(isoString);

  try {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(d);
  } catch {
    return isoString;
  }
}
