export type ClarificationFieldOption = {
  label: string;
  value: string;
};

export type ClarificationFieldType =
  | "text"
  | "textarea"
  | "number"
  | "select"
  | "multi_select"
  | "checkbox"
  | "date"
  | string;

export const SUPPORTED_CLARIFICATION_TYPES = new Set<string>([
  "text",
  "textarea",
  "number",
  "select",
  "multi_select",
  "checkbox",
  "date",
]);

export type ClarificationField = {
  name: string;
  type: ClarificationFieldType;
  label: string;
  required?: boolean;
  description?: string;
  placeholder?: string;
  options?: ClarificationFieldOption[];
  default?: unknown;
};

export type ClarificationRequest = {
  question: string;
  fields: ClarificationField[];
  context?: string;
  schema_version?: number;
};

export type PendingClarification = {
  id: string;
  namespace: readonly string[];
  request: ClarificationRequest;
  supported: boolean;
  raw: unknown;
};

export type ClarificationAnswerPayload = {
  schema_version: number;
  status: "answered";
  values: Record<string, unknown>;
};

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isClarificationInterrupt(value: unknown): boolean {
  if (!isObject(value)) return false;
  if (value.kind === "clarification" || value.type === "clarification") return true;
  return typeof value.question === "string" && Array.isArray(value.fields);
}

export function parseClarifications(
  interrupts: readonly {
    id?: string;
    value?: unknown;
    ns?: readonly string[];
  }[],
): PendingClarification[] {
  const result: PendingClarification[] = [];

  for (const interrupt of interrupts) {
    if (!interrupt.id || !isObject(interrupt.value)) continue;

    if (!isClarificationInterrupt(interrupt.value)) continue;

    const rawFields = Array.isArray(interrupt.value.fields)
      ? interrupt.value.fields
      : [];

    const fields: ClarificationField[] = [];
    for (const f of rawFields) {
      if (!isObject(f) || typeof f.name !== "string") continue;
      const options: ClarificationFieldOption[] = [];
      if (Array.isArray(f.options)) {
        for (const opt of f.options) {
          if (isObject(opt)) {
            const rawVal =
              typeof opt.value !== "undefined"
                ? String(opt.value)
                : typeof opt.label === "string"
                  ? opt.label
                  : "";
            const rawLabel =
              typeof opt.label === "string" ? opt.label : rawVal;
            if (rawVal) {
              options.push({
                label: rawLabel,
                value: rawVal,
              });
            }
          }
        }
      }

      fields.push({
        name: f.name,
        type: typeof f.type === "string" ? f.type : "text",
        label: typeof f.label === "string" ? f.label : f.name,
        required: Boolean(f.required),
        description: typeof f.description === "string" ? f.description : undefined,
        placeholder: typeof f.placeholder === "string" ? f.placeholder : undefined,
        options: options.length > 0 ? options : undefined,
        default: f.default,
      });
    }

    const question =
      typeof interrupt.value.question === "string"
        ? interrupt.value.question
        : "请提供补充信息";

    const context =
      typeof interrupt.value.context === "string"
        ? interrupt.value.context
        : undefined;

    const schemaVersion =
      typeof interrupt.value.schema_version === "number"
        ? interrupt.value.schema_version
        : 1;

    // Support all 7 official clarification field types
    const supported =
      fields.length > 0 &&
      fields.every((field) => SUPPORTED_CLARIFICATION_TYPES.has(field.type));

    result.push({
      id: interrupt.id,
      namespace: interrupt.ns ?? [],
      request: {
        question,
        fields,
        context,
        schema_version: schemaVersion,
      },
      supported,
      raw: interrupt.value,
    });
  }

  return result;
}

export function validateClarificationValues(
  fields: ClarificationField[],
  values: Record<string, unknown>,
): Record<string, string> {
  const errors: Record<string, string> = {};

  for (const field of fields) {
    const rawVal = values[field.name];

    // Check if field type is supported
    if (!SUPPORTED_CLARIFICATION_TYPES.has(field.type)) {
      errors[field.name] = `不支持的字段类型: ${field.type}`;
      continue;
    }

    // Required check
    if (field.required) {
      if (field.type === "checkbox") {
        if (typeof rawVal !== "boolean") {
          errors[field.name] = `请确认${field.label || field.name}`;
          continue;
        }
      } else if (field.type === "multi_select") {
        if (!Array.isArray(rawVal) || rawVal.length === 0) {
          errors[field.name] = `请选择${field.label || field.name}`;
          continue;
        }
      } else if (field.type === "number") {
        const num =
          typeof rawVal === "number"
            ? rawVal
            : typeof rawVal === "string" && rawVal.trim() !== ""
              ? Number(rawVal)
              : NaN;
        if (!Number.isFinite(num)) {
          errors[field.name] = `请填写有效的${field.label || field.name}数值`;
          continue;
        }
      } else {
        const val = typeof rawVal === "string" ? rawVal.trim() : rawVal;
        if (val === undefined || val === null || val === "") {
          errors[field.name] = `请填写${field.label || field.name}`;
          continue;
        }
      }
    }

    // Format & value checks when present
    if (rawVal !== undefined && rawVal !== null && rawVal !== "") {
      if (field.type === "number") {
        const num =
          typeof rawVal === "number"
            ? rawVal
            : typeof rawVal === "string" && rawVal.trim() !== ""
              ? Number(rawVal)
              : NaN;
        if (!Number.isFinite(num)) {
          errors[field.name] = `请填写有效的${field.label || field.name}数值`;
        }
      } else if (field.type === "date") {
        const dateStr = String(rawVal).trim();
        if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
          errors[field.name] = "请输入有效的日期格式 (YYYY-MM-DD)";
        }
      } else if (field.type === "select" && field.options && field.options.length > 0) {
        const matched = field.options.some((opt) => opt.value === String(rawVal));
        if (!matched) {
          errors[field.name] = "请选择有效的选项";
        }
      } else if (field.type === "multi_select") {
        if (!Array.isArray(rawVal)) {
          errors[field.name] = "请选择有效选项";
        } else if (field.options && field.options.length > 0) {
          const validValues = new Set(field.options.map((opt) => opt.value));
          const hasInvalid = rawVal.some((v) => !validValues.has(String(v)));
          if (hasInvalid) {
            errors[field.name] = "存在无效的选项";
          }
        }
      } else if (field.type === "checkbox") {
        if (typeof rawVal !== "boolean") {
          errors[field.name] = "必须为布尔值";
        }
      }
    }
  }

  return errors;
}

export function buildClarificationResponse(
  interruptId: string,
  values: Record<string, unknown>,
  schemaVersion = 1,
): Record<string, ClarificationAnswerPayload> {
  return {
    [interruptId]: {
      schema_version: schemaVersion,
      status: "answered",
      values,
    },
  };
}

export function normalizeClarificationValues(
  fields: ClarificationField[],
  values: Record<string, unknown>,
): Record<string, unknown> {
  const normalized: Record<string, unknown> = {};
  for (const field of fields) {
    const rawVal = values[field.name];
    if (rawVal === undefined || rawVal === null) {
      continue;
    }
    if (field.type === "number") {
      const num = typeof rawVal === "number" ? rawVal : Number(rawVal);
      normalized[field.name] = Number.isFinite(num) ? num : rawVal;
    } else if (field.type === "checkbox") {
      normalized[field.name] = Boolean(rawVal);
    } else if (field.type === "multi_select") {
      normalized[field.name] = Array.isArray(rawVal) ? rawVal.map(String) : [];
    } else if (
      field.type === "date" ||
      field.type === "select" ||
      field.type === "text" ||
      field.type === "textarea"
    ) {
      normalized[field.name] = String(rawVal);
    } else {
      normalized[field.name] = rawVal;
    }
  }
  return normalized;
}
