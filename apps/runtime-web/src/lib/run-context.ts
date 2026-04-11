function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseRunContextText(
  text: string,
): Record<string, unknown> | undefined {
  const trimmed = text.trim();
  if (!trimmed) {
    return undefined;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to parse JSON.";
    throw new Error(message);
  }

  if (!isRecord(parsed)) {
    throw new Error("Run context must be a JSON object.");
  }

  return parsed;
}

export function formatRunContextText(text: string): string {
  const parsed = parseRunContextText(text);
  return parsed ? JSON.stringify(parsed, null, 2) : "";
}

function normalizeStorageSegment(value: string | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "__default__";
  }
  return encodeURIComponent(trimmed);
}

export function buildRunContextStorageKey({
  apiUrl,
  targetType,
  targetId,
}: {
  apiUrl?: string;
  targetType?: string;
  targetId?: string;
}): string {
  return [
    "runtime-web",
    "run-context",
    normalizeStorageSegment(apiUrl),
    normalizeStorageSegment(targetType),
    normalizeStorageSegment(targetId),
  ].join(":");
}

export function mergeRunContexts(
  artifactContext?: Record<string, unknown>,
  manualRunContext?: Record<string, unknown>,
): Record<string, unknown> | undefined {
  const merged = {
    ...(artifactContext ?? {}),
    ...(manualRunContext ?? {}),
  };
  return Object.keys(merged).length > 0 ? merged : undefined;
}
