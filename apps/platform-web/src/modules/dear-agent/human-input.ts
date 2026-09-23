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
  if (typeof value.question === "string" && Array.isArray(value.fields)) return true;
  if (Array.isArray(value.questions) && value.questions.length > 0) return true;
  if (
    typeof value.question === "string" &&
    (Array.isArray(value.options) || typeof value.is_multi_select === "boolean")
  ) {
    return true;
  }
  if (
    typeof value.question === "string" &&
    !Array.isArray(value.action_requests) &&
    !Array.isArray(value.review_configs)
  ) {
    return true;
  }
  return false;
}

function parseFieldOptions(rawOptions: unknown): ClarificationFieldOption[] {
  if (!Array.isArray(rawOptions)) return [];
  const options: ClarificationFieldOption[] = [];
  for (const opt of rawOptions) {
    if (typeof opt === "string") {
      const val = opt.trim();
      if (val) {
        options.push({ label: val, value: val });
      }
    } else if (isObject(opt)) {
      const rawVal =
        typeof opt.value !== "undefined"
          ? String(opt.value)
          : typeof opt.label === "string"
            ? opt.label
            : "";
      const rawLabel = typeof opt.label === "string" ? opt.label : rawVal;
      if (rawVal) {
        options.push({ label: rawLabel, value: rawVal });
      }
    }
  }
  return options;
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

    const val = interrupt.value;
    const fields: ClarificationField[] = [];
    let topQuestion = "请提供补充信息";
    const context = typeof val.context === "string" ? val.context : undefined;
    const schemaVersion =
      typeof val.schema_version === "number" ? val.schema_version : 1;

    if (Array.isArray(val.fields)) {
      if (typeof val.question === "string" && val.question.trim()) {
        topQuestion = val.question.trim();
      }
      for (const f of val.fields) {
        if (!isObject(f) || typeof f.name !== "string") continue;
        const options = parseFieldOptions(f.options);
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
    } else if (Array.isArray(val.questions) && val.questions.length > 0) {
      const qList = val.questions;
      if (typeof val.question === "string" && val.question.trim()) {
        topQuestion = val.question.trim();
      } else if (qList.length === 1 && isObject(qList[0]) && typeof qList[0].question === "string") {
        topQuestion = qList[0].question.trim();
      }

      qList.forEach((q, idx) => {
        if (!isObject(q)) return;
        const qTitle = typeof q.question === "string" ? q.question.trim() : `问题 ${idx + 1}`;
        const options = parseFieldOptions(q.options);
        const isMulti = Boolean(q.is_multi_select);
        const fieldType: ClarificationFieldType = isMulti
          ? "multi_select"
          : options.length > 0
            ? "select"
            : "text";
        const fieldName =
          typeof q.name === "string" && q.name.trim()
            ? q.name.trim()
            : qList.length === 1
              ? "selection"
              : `question_${idx}`;

        fields.push({
          name: fieldName,
          type: fieldType,
          label: qTitle,
          required: Boolean(q.required),
          description: typeof q.description === "string" ? q.description : undefined,
          options: options.length > 0 ? options : undefined,
          default: isMulti ? [] : options[0]?.value ?? "",
        });
      });
    } else if (typeof val.question === "string") {
      topQuestion = val.question.trim();
      const options = parseFieldOptions(val.options);
      const isMulti = Boolean(val.is_multi_select);
      const fieldType: ClarificationFieldType = isMulti
        ? "multi_select"
        : options.length > 0
          ? "select"
          : "textarea";

      fields.push({
        name: "answer",
        type: fieldType,
        label: topQuestion,
        required: true,
        options: options.length > 0 ? options : undefined,
        default: isMulti ? [] : options[0]?.value ?? "",
      });
    }

    const supported =
      fields.length > 0 &&
      fields.every((field) => SUPPORTED_CLARIFICATION_TYPES.has(field.type));

    result.push({
      id: interrupt.id,
      namespace: interrupt.ns ?? [],
      request: {
        question: topQuestion,
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

    if (!SUPPORTED_CLARIFICATION_TYPES.has(field.type)) {
      errors[field.name] = `不支持的字段类型: ${field.type}`;
      continue;
    }

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
  rawInterrupt?: unknown,
): Record<string, unknown> {
  // 包含 questions 数组的自定义提问中断（非原生 kind: "clarification"）
  if (
    isObject(rawInterrupt) &&
    rawInterrupt.kind !== "clarification" &&
    Array.isArray(rawInterrupt.questions)
  ) {
    const answers = Object.values(values);
    return {
      [interruptId]: {
        answers,
        values,
        ...(answers.length === 1 ? { answer: answers[0] } : {}),
      },
    };
  }

  // 默认标准答复格式
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

export function isClarificationActive(
  clarification: PendingClarification,
  messages: readonly unknown[],
  resolvedIds?: ReadonlySet<string>,
): boolean {
  if (resolvedIds?.has(clarification.id)) {
    return false;
  }
  if (!Array.isArray(messages) || messages.length === 0) {
    return true;
  }

  // 1. 收集所有已完成的 ToolMessage tool_call_id
  const completedToolCallIds = new Set<string>();
  for (const msg of messages) {
    if (!msg || typeof msg !== "object") continue;
    const m = msg as Record<string, unknown>;
    const type =
      typeof m._getType === "function"
        ? (m as { _getType: () => string })._getType()
        : m.type;
    if (type === "tool") {
      const toolCallId = m.tool_call_id;
      if (typeof toolCallId === "string" && toolCallId.trim()) {
        completedToolCallIds.add(toolCallId.trim());
      }
    }
  }

  // 2. 检查 messages 中是否存在匹配该澄清的工具调用（兼容 request_information / ask_user_question 等，以及 interrupt.id 与 tool_call.id 不一致的场景）
  const clarificationToolNames = new Set([
    "request_information",
    "ask_user_question",
    "ask_question",
    "clarify",
  ]);
  let foundMatchingCall = false;
  let hasPendingMatchingCall = false;
  let clarifyingAiIndex = -1;
  let lastClarificationCallAiIndex = -1;
  let lastClarificationCallCompleted = false;

  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (!msg || typeof msg !== "object") continue;
    const m = msg as Record<string, unknown>;
    const type =
      typeof m._getType === "function"
        ? (m as { _getType: () => string })._getType()
        : m.type;

    if (type === "ai" && Array.isArray(m.tool_calls)) {
      for (const rawCall of m.tool_calls) {
        if (!rawCall || typeof rawCall !== "object") continue;
        const call = rawCall as Record<string, unknown>;
        const callName = typeof call.name === "string" ? call.name.trim() : "";
        const args = (call.args && typeof call.args === "object" ? call.args : {}) as Record<string, unknown>;
        if (clarificationToolNames.has(callName) || isClarificationInterrupt(args)) {
          const callId = typeof call.id === "string" ? call.id.trim() : "";
          const isCompleted = Boolean(callId && completedToolCallIds.has(callId));
          if (lastClarificationCallAiIndex === -1) {
            lastClarificationCallAiIndex = i;
            lastClarificationCallCompleted = isCompleted;
          }

          const qText = typeof args.question === "string" ? args.question.trim() : "";
          const firstQ =
            Array.isArray(args.questions) && isObject(args.questions[0]) && typeof args.questions[0].question === "string"
              ? args.questions[0].question.trim()
              : "";
          const clarQText = clarification.request.question.trim();

          const matches =
            (callId && callId === clarification.id) ||
            (!callId && !clarQText) ||
            (qText && clarQText && qText === clarQText) ||
            (firstQ && clarQText && firstQ === clarQText) ||
            (callId && clarification.id.includes(callId));

          if (matches) {
            foundMatchingCall = true;
            if (clarifyingAiIndex === -1) {
              clarifyingAiIndex = i;
            }
            if (!callId || !completedToolCallIds.has(callId)) {
              hasPendingMatchingCall = true;
            }
          }
        }
      }
    }
  }

  // 如果找到了匹配该澄清的工具调用，且已全部有 ToolMessage 结果，说明已被回答消费
  if (foundMatchingCall && !hasPendingMatchingCall) {
    return false;
  }

  // 如果 interrupt.id 与 tool_call.id 不同导致未精确命中，但消息历史中最后一次澄清工具调用已有 ToolMessage 结果，说明也已被消费
  if (!foundMatchingCall && lastClarificationCallAiIndex !== -1 && lastClarificationCallCompleted) {
    return false;
  }

  // 3. 检查回合推进：如果该澄清所在 AI 消息（或最后一次澄清调用）之后已有新的人类输入，说明该轮次早已结束
  const anchorAiIndex = clarifyingAiIndex !== -1 ? clarifyingAiIndex : lastClarificationCallAiIndex;
  if (anchorAiIndex !== -1) {
    for (let i = anchorAiIndex + 1; i < messages.length; i++) {
      const msg = messages[i];
      if (!msg || typeof msg !== "object") continue;
      const m = msg as Record<string, unknown>;
      const type =
        typeof m._getType === "function"
          ? (m as { _getType: () => string })._getType()
          : m.type;
      if (type === "human") {
        return false;
      }
    }
  }

  return true;
}

export function filterActiveClarifications(
  clarifications: readonly PendingClarification[],
  messages: readonly unknown[],
  resolvedIds?: ReadonlySet<string>,
): PendingClarification[] {
  return clarifications.filter((c) =>
    isClarificationActive(c, messages, resolvedIds),
  );
}
