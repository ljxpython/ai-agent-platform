export type DecisionKind = "approve" | "reject" | "edit";
export type ReviewAction = {
  name: string;
  args: Record<string, unknown>;
  allowed: DecisionKind[];
};
export type PendingReview = {
  id: string;
  namespace: readonly string[];
  actions: ReviewAction[];
  fingerprint: string;
  supported: boolean;
  raw: unknown;
};
export type ReviewDraft = {
  type?: DecisionKind;
  args?: string;
  message?: string;
};

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (object(value))
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical(value[key])]),
    );
  return value;
}

export function parseReviews(
  interrupts: readonly {
    id?: string;
    value?: unknown;
    ns?: readonly string[];
  }[],
): PendingReview[] {
  return interrupts.map((interrupt) => {
    const value = object(interrupt.value) ? interrupt.value : {};
    const requests = Array.isArray(value.action_requests)
      ? value.action_requests
      : [];
    const configs = Array.isArray(value.review_configs)
      ? value.review_configs
      : [];
    const actions: ReviewAction[] = [];
    for (const request of requests) {
      if (
        !object(request) ||
        typeof request.name !== "string" ||
        !object(request.args)
      )
        continue;
      const config = configs.find(
        (entry) => object(entry) && entry.action_name === request.name,
      );
      const allowed =
        object(config) && Array.isArray(config.allowed_decisions)
          ? config.allowed_decisions.filter((kind): kind is DecisionKind =>
              ["approve", "reject", "edit"].includes(String(kind)),
            )
          : [];
      actions.push({ name: request.name, args: request.args, allowed });
    }
    const details = Object.fromEntries(
      Object.entries(value).filter(
        ([key]) =>
          ![
            "action_requests",
            "actionRequests",
            "review_configs",
            "reviewConfigs",
          ].includes(key),
      ),
    );
    return {
      id: interrupt.id ?? "",
      namespace: interrupt.ns ?? [],
      actions,
      fingerprint: JSON.stringify(canonical({ actions, details })),
      raw: interrupt.value,
      supported:
        Boolean(interrupt.id) &&
        actions.length > 0 &&
        actions.length === requests.length &&
        actions.every((action) => action.allowed.length > 0),
    };
  });
}

function validateEdited(original: unknown, edited: unknown): void {
  if (original === null) {
    if (edited !== null) throw new Error("不能改变参数类型");
  } else if (Array.isArray(original)) {
    if (!Array.isArray(edited)) throw new Error("参数必须为数组");
    if (!original.length && edited.length)
      throw new Error("缺少数组元素类型，无法安全编辑");
    edited.forEach((item, index) =>
      validateEdited(original[index] ?? original[0], item),
    );
  } else if (object(original)) {
    if (!object(edited)) throw new Error("参数必须为对象");
    if (
      Object.keys(original).length !== Object.keys(edited).length ||
      Object.keys(edited).some(
        (key) =>
          !Object.prototype.hasOwnProperty.call(original, key) ||
          ["__proto__", "constructor", "prototype"].includes(key),
      )
    ) {
      throw new Error("只能修改原有参数，不能增删参数或注入配置");
    }
    for (const key of Object.keys(original))
      validateEdited(original[key], edited[key]);
  } else if (
    typeof original !== typeof edited ||
    (typeof edited === "number" && !Number.isFinite(edited))
  ) {
    throw new Error("不能改变参数类型");
  }
}

export function buildReviewResponses(
  reviews: PendingReview[],
  drafts: Record<string, ReviewDraft[]>,
) {
  const responses: Record<string, { decisions: Record<string, unknown>[] }> =
    Object.create(null) as Record<
      string,
      { decisions: Record<string, unknown>[] }
    >;
  if (!reviews.length) throw new Error("没有待审批操作");
  for (const review of reviews) {
    if (
      !review.supported ||
      Object.prototype.hasOwnProperty.call(responses, review.id)
    )
      throw new Error("不支持或重复的审批请求");
    const selected = drafts[review.id];
    if (selected?.length !== review.actions.length)
      throw new Error("请逐项选择决策");
    responses[review.id] = {
      decisions: review.actions.map((action, index) => {
        const draft = selected[index];
        if (!draft?.type || !action.allowed.includes(draft.type))
          throw new Error("请为每项操作选择允许的决策");
        if (draft.type === "edit") {
          let args: unknown;
          try {
            args = JSON.parse(draft.args ?? "");
          } catch {
            throw new Error("编辑参数必须为有效 JSON");
          }
          validateEdited(action.args, args);
          return { type: "edit", edited_action: { name: action.name, args } };
        }
        if (draft.type === "reject") {
          const message = draft.message?.trim() ?? "";
          if (!message || message.length > 2000)
            throw new Error("拒绝原因须为 1–2000 个字符");
          return { type: "reject", message };
        }
        return { type: "approve" };
      }),
    };
  }
  return responses;
}
