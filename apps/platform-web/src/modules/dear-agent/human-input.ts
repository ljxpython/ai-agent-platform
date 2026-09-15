export type ClarificationFieldOption = {
  label: string;
  value: string;
};

export type ClarificationFieldType = "text" | "select" | string;

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
  if (value.kind === "clarification") return true;
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
          if (isObject(opt) && typeof opt.value !== "undefined") {
            options.push({
              label: typeof opt.label === "string" ? opt.label : String(opt.value),
              value: String(opt.value),
            });
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

    // P1: support text and select
    const supported =
      fields.length > 0 &&
      fields.every((field) => ["text", "select"].includes(field.type));

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
    const val = typeof rawVal === "string" ? rawVal.trim() : rawVal;

    if (field.required) {
      if (val === undefined || val === null || val === "") {
        errors[field.name] = `请填写${field.label || field.name}`;
        continue;
      }
    }

    if (val !== undefined && val !== null && val !== "") {
      if (field.type === "select" && field.options && field.options.length > 0) {
        const matched = field.options.some((opt) => opt.value === String(val));
        if (!matched) {
          errors[field.name] = `请选择有效的选项`;
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
