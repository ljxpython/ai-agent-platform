import { isAxiosError } from "axios";
import { hasStoredAuthSession } from "@/services/auth/token";

export interface PlatformValidationDetail {
  loc?: Array<string | number>;
  message?: string;
  type?: string;
}

export interface PlatformHttpError {
  status: number | null;
  code?: string;
  message: string;
  requestId?: string;
  details?: PlatformValidationDetail[];
  extra?: Record<string, unknown>;
  cancelled: boolean;
}

export interface PlatformUnwrappedHttpError extends Error {
  code?: string;
  requestId?: string;
  status?: number;
  details?: PlatformValidationDetail[];
  extra?: Record<string, unknown>;
  cancelled?: boolean;
}

const MAX_ERROR_BYTES = 64 * 1024;
const REQUEST_ID = /^[A-Za-z0-9._-]{1,128}$/;

function object(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function status(value: unknown): number | null {
  return typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 100 &&
    value <= 599
    ? value
    : null;
}

function envelope(raw: unknown) {
  const record = object(raw);
  const nested = object(record?.error);
  const meta = object(record?.meta);
  const message = [
    nested?.message,
    record?.message,
    record?.detail,
    record?.error,
  ]
    .find(
      (value): value is string =>
        typeof value === "string" && Boolean(value.trim()),
    )
    ?.trim();
  const code = [nested?.code, record?.code]
    .find(
      (value): value is string =>
        typeof value === "string" && Boolean(value.trim()),
    )
    ?.trim();
  const id = record?.request_id ?? meta?.request_id ?? record?.requestId;
  const requestId =
    typeof id === "string" && REQUEST_ID.test(id) ? id : undefined;
  const rawDetails = nested?.details ?? record?.details;
  const details = Array.isArray(rawDetails)
    ? rawDetails
        .slice(0, 20)
        .filter((item): item is PlatformValidationDetail =>
          Boolean(object(item)),
        )
    : undefined;
  const extra = object(nested?.extra ?? record?.extra);
  return { message, code, requestId, details, extra };
}

function safeJson(text: unknown): unknown {
  if (
    typeof text !== "string" ||
    new TextEncoder().encode(text).length > MAX_ERROR_BYTES
  )
    return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export function extractPlatformHttpError(
  err: unknown,
  fallbackMessage = "请求失败",
): PlatformHttpError {
  const source = object(err);
  const response = object(source?.response);
  const httpStatus =
    status(response?.status) ??
    status(source?.status) ??
    status(source?.statusCode);
  const parsedStatus =
    httpStatus ??
    (typeof source?.message === "string"
      ? status(
          Number(
            source.message.match(
              /(?:Protocol request failed|HTTP)\s*:?\s*(\d{3})/i,
            )?.[1],
          ),
        )
      : null);
  const cancelled =
    (isAxiosError(err) && err.code === "ERR_CANCELED") ||
    (err instanceof Error && err.name === "AbortError");
  const direct =
    err instanceof Error &&
    !source?.code &&
    !source?.requestId &&
    !source?.extra
      ? undefined
      : err;
  const fields = envelope(response?.data ?? safeJson(source?.text) ?? direct);
  const rawMessage =
    (fields.message && !/<(?:!doctype|html|script)[\s>]/i.test(fields.message)
      ? fields.message
      : undefined) ||
    (response || source?.text
      ? undefined
      : !isAxiosError(err) &&
          !(err instanceof TypeError) &&
          typeof source?.message === "string" &&
          !/(Protocol request failed|HTTPError|HTTP\s*\d|[{<]html)/i.test(
            source.message,
          )
        ? source.message
        : undefined);
  const message =
    rawMessage ||
    (parsedStatus
      ? `请求失败（HTTP ${parsedStatus}）`
      : cancelled
        ? fallbackMessage
        : (isAxiosError(err) && !response) || err instanceof TypeError
          ? "网络连接失败，请检查网络后重试"
          : fallbackMessage);
  return {
    status: parsedStatus,
    code: fields.code,
    message,
    requestId: fields.requestId,
    details: fields.details,
    extra: fields.extra,
    cancelled,
  };
}

export function formatPlatformHttpErrorMessage(
  error: unknown,
  fallbackMessage = "请求失败",
): string {
  const result = extractPlatformHttpError(error, fallbackMessage);
  if (
    result.cancelled ||
    !result.requestId ||
    result.message.includes(`请求编号：${result.requestId}`)
  )
    return result.message;
  return `${result.message}（请求编号：${result.requestId}）`;
}

export async function unwrapPlatformHttpError(
  err: unknown,
  fallbackMessage = "请求失败",
): Promise<PlatformUnwrappedHttpError> {
  const source = object(err);
  const response = object(source?.response);
  let payload = response?.data;
  if (payload instanceof Blob) {
    if (payload.size <= MAX_ERROR_BYTES) {
      const blob = payload;
      const text =
        typeof blob.text === "function"
          ? await blob.text()
          : await new Promise<string>((resolve) => {
              const reader = new FileReader();
              reader.onload = () =>
                resolve(typeof reader.result === "string" ? reader.result : "");
              reader.onerror = () => resolve("");
              reader.readAsText(blob);
            });
      payload = safeJson(text);
    } else payload = undefined;
  }
  const normalized = response
    ? { ...source, response: { ...response, data: payload } }
    : err;
  const fields = extractPlatformHttpError(normalized, fallbackMessage);
  const result = new Error(
    formatPlatformHttpErrorMessage(normalized, fallbackMessage),
  ) as PlatformUnwrappedHttpError;
  result.name = fields.cancelled ? "AbortError" : "Error";
  result.code = fields.code;
  result.status = fields.status ?? undefined;
  result.requestId = fields.requestId;
  result.details = fields.details;
  result.extra = fields.extra;
  result.cancelled = fields.cancelled;
  return result;
}

export function resolvePlatformHttpErrorMessage(
  error: unknown,
  fallbackMessage: string,
  resourceLabel: string,
): string {
  const fields = extractPlatformHttpError(error, fallbackMessage);
  let message = fields.message;
  if (!hasStoredAuthSession())
    message = "当前登录态缺少控制面会话。请重新登录后再试。";
  else if (fields.status === 401)
    message = "当前登录态已失效，请重新登录后再试。";
  else if (fields.status === 403)
    message = `当前账号没有访问${resourceLabel}的权限。`;
  else if (fields.status === 404)
    message =
      fields.code === "route_not_found"
        ? `${resourceLabel}接口不存在，先确认前端环境是否已接到 platform-api。`
        : `${resourceLabel}不存在或无权访问。`;
  else if (fields.status && fields.status >= 500 && !fields.code)
    message = `${resourceLabel}后端处理失败，请查看 platform-api 日志。`;
  return fields.requestId &&
    !fields.cancelled &&
    !message.includes(`请求编号：${fields.requestId}`)
    ? `${message}（请求编号：${fields.requestId}）`
    : message;
}
