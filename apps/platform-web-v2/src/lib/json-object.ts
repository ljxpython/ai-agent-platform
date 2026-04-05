export function parseJsonObject(
  raw: string,
  fieldName: string,
): Record<string, unknown> {
  const normalized = raw.trim();
  if (!normalized) {
    return {};
  }

  const parsed = JSON.parse(normalized);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${fieldName} must be a JSON object`);
  }

  return parsed as Record<string, unknown>;
}

export function stringifyJsonObject(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}
