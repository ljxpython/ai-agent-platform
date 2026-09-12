import { readonly, shallowRef } from "vue";

type ActionStatus = "submitting" | "acknowledged" | "unknown" | "rejected";
export type RunAction = {
  readonly key: string;
  readonly threadId: string;
  readonly kind: "send" | "resume" | "fork";
  readonly input: string;
  readonly url?: string;
  readonly body?: string;
  readonly runId?: string;
  readonly status: ActionStatus;
};

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("无效的运行请求");
  return value as Record<string, unknown>;
}

/** Convert the official SDK batch format to the platform's public resume map. */
export function platformCommand(body: string, threadId?: string): string {
  const command = record(JSON.parse(body));
  if (!Number.isInteger(command.id)) throw new Error("运行命令 ID 必须为整数");
  if (command.method === "run.start") {
    const params = record(command.params);
    const config = params.config == null ? {} : record(params.config);
    const configurable =
      config.configurable == null ? {} : record(config.configurable);
    if ("thread_id" in configurable) {
      if (configurable.thread_id !== threadId)
        throw new Error("运行请求线程不一致");
      // The SDK repeats the URL thread in config; the gateway accepts URL scope only.
      const { thread_id: _threadId, ...options } = configurable;
      return JSON.stringify({
        ...command,
        params: { ...params, config: { ...config, configurable: options } },
      });
    }
    return body;
  }
  if (command.method !== "input.respond") throw new Error("不支持的运行命令");
  const params = record(command.params);
  const forbidden = Object.keys(params).filter(
    (key) =>
      ![
        "responses",
        "interrupt_id",
        "response",
        "namespace",
        "assistant_id",
      ].includes(key),
  );
  if (forbidden.length) throw new Error("审批请求不能覆盖运行参数");
  const resume: Record<string, unknown> = Object.create(null) as Record<
    string,
    unknown
  >;
  const entries = Array.isArray(params.responses) ? params.responses : [params];
  for (const value of entries) {
    const entry = record(value);
    const id = entry.interrupt_id;
    if (
      typeof id !== "string" ||
      !id.trim() ||
      Object.prototype.hasOwnProperty.call(resume, id)
    )
      throw new Error("审批 ID 缺失或重复");
    if (!Object.prototype.hasOwnProperty.call(entry, "response"))
      throw new Error("审批决策缺失");
    if (
      Object.keys(entry).some(
        (key) =>
          !["interrupt_id", "response", "namespace", "assistant_id"].includes(
            key,
          ),
      )
    ) {
      throw new Error("审批请求包含不支持的字段");
    }
    resume[id] = entry.response;
  }
  if (!entries.length) throw new Error("请选择审批决策");
  return JSON.stringify({ ...command, params: { resume } });
}

/** A session-local HTTP action receipt; execution state stays in the SDK. */
export function createRunActions(
  projectId: string,
  authorizedFetch: typeof fetch,
) {
  const current = shallowRef<RunAction | null>(null);
  let disposed = false;
  const controller = new AbortController();

  function begin(threadId: string, kind: RunAction["kind"], input: unknown) {
    if (disposed) throw new Error("会话已关闭");
    if (
      current.value &&
      ["submitting", "unknown"].includes(current.value.status)
    ) {
      throw new Error("请先核实上一动作的结果");
    }
    current.value = Object.freeze({
      key: `run:${crypto.randomUUID()}`,
      threadId,
      kind,
      input: JSON.stringify(input),
      status: "submitting",
    });
    return current.value;
  }

  async function dispatch(
    action: RunAction,
    init: RequestInit = {},
  ): Promise<Response> {
    if (disposed || !action.url || !action.body)
      throw new Error("原始请求尚未建立");
    const headers = new Headers(init.headers);
    headers.set("x-project-id", projectId);
    headers.set("Idempotency-Key", action.key);
    headers.set("content-type", "application/json");
    try {
      const response = await authorizedFetch(action.url, {
        ...init,
        method: "POST",
        headers,
        body: action.body,
        signal: init.signal
          ? AbortSignal.any([controller.signal, init.signal])
          : controller.signal,
      });
      let runId: string | undefined;
      let protocolError = false;
      if (response.ok) {
        const payload = (await response.clone().json()) as {
          type?: string;
          run_id?: string;
          result?: { run_id?: string };
        };
        protocolError = payload.type === "error";
        runId = payload.result?.run_id ?? payload.run_id;
      }
      if (!disposed && current.value?.key === action.key) {
        current.value = Object.freeze({
          ...action,
          runId,
          status:
            response.ok && !protocolError && runId
              ? "acknowledged"
              : response.ok && !protocolError
                ? "unknown"
                : response.status >= 500 || response.status === 408
                  ? "unknown"
                  : "rejected",
        });
      }
      return response;
    } catch (error) {
      if (!disposed && current.value?.key === action.key)
        current.value = Object.freeze({ ...action, status: "unknown" });
      throw error;
    }
  }

  const fetch: typeof globalThis.fetch = async (input, init) => {
    if (disposed) throw new Error("会话已关闭");
    const url = input instanceof Request ? input.url : input.toString();
    const method = (
      init?.method ?? (input instanceof Request ? input.method : "GET")
    ).toUpperCase();
    const path = new URL(url).pathname;
    if (method === "POST" && /\/threads\/[^/]+\/commands\/?$/.test(path)) {
      const action = current.value;
      if (
        !action ||
        !path.endsWith(
          `/threads/${encodeURIComponent(action.threadId)}/commands`,
        )
      ) {
        throw new Error("运行请求未绑定当前会话动作");
      }
      const raw =
        typeof init?.body === "string"
          ? init.body
          : input instanceof Request
            ? await input.clone().text()
            : "";
      const body = platformCommand(raw, action.threadId);
      if (action.body && action.body !== body)
        throw new Error("重试不能修改原始请求");
      const snapshot = Object.freeze({ ...action, url, body });
      current.value = snapshot;
      return dispatch(snapshot, init);
    }
    const headers = new Headers(
      input instanceof Request ? input.headers : undefined,
    );
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    headers.set("x-project-id", projectId);
    const signal = init?.signal ?? (input instanceof Request ? input.signal : null);
    return authorizedFetch(input, {
      ...init,
      headers,
      signal: signal
        ? AbortSignal.any([controller.signal, signal])
        : controller.signal,
    });
  };

  function acknowledge(key?: string, runId?: string) {
    if (disposed) return;
    if (!current.value || (key && current.value.key !== key)) return;
    current.value = Object.freeze({
      ...current.value,
      runId: runId ?? current.value.runId,
      status: "acknowledged",
    });
  }

  function rejectUnsent() {
    if (current.value?.status === "submitting" && !current.value.body) {
      current.value = Object.freeze({ ...current.value, status: "rejected" });
    }
  }

  async function retry() {
    const action = current.value;
    if (!action || action.status !== "unknown")
      throw new Error("没有需要核实的原始请求");
    current.value = Object.freeze({ ...action, status: "submitting" });
    return dispatch(action);
  }

  async function fork(
    apiUrl: string,
    threadId: string,
    payload: Record<string, unknown>,
  ) {
    const action = begin(threadId, "fork", payload);
    const snapshot = Object.freeze({
      ...action,
      url: `${apiUrl}/threads/${encodeURIComponent(threadId)}/runs`,
      body: action.input,
    });
    current.value = snapshot;
    return dispatch(snapshot);
  }

  function dispose() {
    disposed = true;
    controller.abort();
    current.value = null;
  }
  return {
    current: readonly(current),
    begin,
    fetch,
    retry,
    fork,
    acknowledge,
    rejectUnsent,
    dispose,
  };
}
