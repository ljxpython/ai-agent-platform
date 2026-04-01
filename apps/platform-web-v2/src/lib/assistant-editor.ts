import type { AssistantParameterSchema } from "@/lib/management-api/assistants";

import { parseJsonObject } from "@/lib/json-object";

export type AssistantConfigField = {
  key: string;
  type: string;
  required: boolean;
};

export function getAssistantConfigFields(
  schema: AssistantParameterSchema | null | undefined,
): AssistantConfigField[] {
  const sections = Array.isArray(schema?.sections) ? schema.sections : [];
  const configSection = sections.find((section) => section?.key === "config");
  const properties = configSection?.properties;
  if (!properties || typeof properties !== "object") {
    return [];
  }

  return Object.entries(properties).map(([key, value]) => ({
    key,
    type: typeof value?.type === "string" ? value.type : "string",
    required: Boolean(value?.required),
  }));
}

export function buildAssistantConfigFieldValues(
  rawConfig: string,
  fields: AssistantConfigField[],
): Record<string, string> {
  const baseConfig = parseJsonObject(rawConfig, "config");
  const nextFields: Record<string, string> = {};
  for (const field of fields) {
    const rawValue = baseConfig[field.key];
    nextFields[field.key] =
      rawValue === null || rawValue === undefined
        ? ""
        : typeof rawValue === "string"
          ? rawValue
          : String(rawValue);
  }
  return nextFields;
}

export function applyAssistantConfigFieldValue(
  rawConfig: string,
  key: string,
  value: string,
  valueType: string,
): string {
  const currentConfig = parseJsonObject(rawConfig, "config");
  if (!value.trim()) {
    delete currentConfig[key];
    return JSON.stringify(currentConfig, null, 2);
  }

  if (valueType === "number") {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      throw new Error(`config.${key} must be a valid number`);
    }
    currentConfig[key] = parsed;
    return JSON.stringify(currentConfig, null, 2);
  }

  if (valueType === "boolean") {
    currentConfig[key] = value === "true";
    return JSON.stringify(currentConfig, null, 2);
  }

  currentConfig[key] = value;
  return JSON.stringify(currentConfig, null, 2);
}
