"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  applyAssistantConfigFieldValue,
  buildAssistantConfigFieldValues,
  getAssistantConfigFields,
} from "@/lib/assistant-editor";
import { EmptyState } from "@/components/platform/empty-state";
import { FormSection } from "@/components/platform/form-section";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  createAssistant,
  getAssistantParameterSchema,
  type AssistantParameterSchema,
} from "@/lib/management-api/assistants";
import {
  listGraphsPage,
  type ManagementGraph,
} from "@/lib/management-api/graphs";
import {
  listRuntimeModels,
  listRuntimeTools,
  type RuntimeModelItem,
  type RuntimeToolItem,
} from "@/lib/management-api/runtime";
import { parseJsonObject } from "@/lib/json-object";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

const FORM_ID = "create-assistant-form";

function buildCreateAssistantPayload(input: {
  assistantId: string;
  config: string;
  context: string;
  description: string;
  graphId: string;
  metadata: string;
  name: string;
  runtimeEnableTools: boolean;
  runtimeModelId: string;
  runtimeToolNames: string[];
}) {
  const configObject = parseJsonObject(input.config, "config");
  const contextObject = parseJsonObject(input.context, "context");
  const metadataObject = parseJsonObject(input.metadata, "metadata");
  const configurableRaw =
    configObject &&
    typeof configObject.configurable === "object" &&
    !Array.isArray(configObject.configurable)
      ? (configObject.configurable as Record<string, unknown>)
      : {};
  const configurable: Record<string, unknown> = { ...configurableRaw };

  const trimmedModelId = input.runtimeModelId.trim();
  if (trimmedModelId) {
    configurable.model_id = trimmedModelId;
  } else {
    delete configurable.model_id;
  }

  const cleanedTools = input.runtimeToolNames
    .map((name) => name.trim())
    .filter((name) => name.length > 0);
  if (input.runtimeEnableTools && cleanedTools.length > 0) {
    configurable.enable_tools = true;
    configurable.tools = cleanedTools;
  } else {
    delete configurable.enable_tools;
    delete configurable.tools;
  }

  if (Object.keys(configurable).length > 0) {
    configObject.configurable = configurable;
  } else {
    delete (configObject as Record<string, unknown>).configurable;
  }

  const payload: {
    assistant_id?: string;
    config?: Record<string, unknown>;
    context?: Record<string, unknown>;
    description?: string;
    graph_id: string;
    metadata?: Record<string, unknown>;
    name: string;
  } = {
    graph_id: input.graphId.trim(),
    name: input.name.trim(),
  };

  if (input.description.trim()) {
    payload.description = input.description.trim();
  }
  if (input.assistantId.trim()) {
    payload.assistant_id = input.assistantId.trim();
  }
  if (Object.keys(configObject).length > 0) {
    payload.config = configObject;
  }
  if (Object.keys(contextObject).length > 0) {
    payload.context = contextObject;
  }
  if (Object.keys(metadataObject).length > 0) {
    payload.metadata = metadataObject;
  }

  return payload;
}

export default function CreateAssistantPage() {
  const router = useRouter();
  const { currentProject, projectId } = useWorkspaceContext();

  const [graphId, setGraphId] = useState("assistant");
  const [graphOptions, setGraphOptions] = useState<ManagementGraph[]>([]);
  const [graphLoading, setGraphLoading] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [assistantId, setAssistantId] = useState("");
  const [config, setConfig] = useState("{}");
  const [context, setContext] = useState("{}");
  const [metadata, setMetadata] = useState("{}");
  const [schema, setSchema] = useState<AssistantParameterSchema | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [configFields, setConfigFields] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runtimeModels, setRuntimeModels] = useState<RuntimeModelItem[]>([]);
  const [runtimeTools, setRuntimeTools] = useState<RuntimeToolItem[]>([]);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [runtimeModelId, setRuntimeModelId] = useState("");
  const [runtimeEnableTools, setRuntimeEnableTools] = useState(false);
  const [runtimeToolNames, setRuntimeToolNames] = useState<string[]>([]);

  const sortedGraphOptions = useMemo(
    () =>
      [...graphOptions].sort((left, right) =>
        left.graph_id.localeCompare(right.graph_id),
      ),
    [graphOptions],
  );
  const configPropertyDefs = useMemo(
    () => getAssistantConfigFields(schema),
    [schema],
  );

  const requestPreview = useMemo(() => {
    try {
      return {
        error: null,
        payload: buildCreateAssistantPayload({
          assistantId,
          config,
          context,
          description,
          graphId,
          metadata,
          name,
          runtimeEnableTools,
          runtimeModelId,
          runtimeToolNames,
        }),
      };
    } catch (previewError) {
      return {
        error:
          previewError instanceof Error
            ? previewError.message
            : "Invalid request payload",
        payload: null,
      };
    }
  }, [
    assistantId,
    config,
    context,
    description,
    graphId,
    metadata,
    name,
    runtimeEnableTools,
    runtimeModelId,
    runtimeToolNames,
  ]);

  useEffect(() => {
    if (!projectId) {
      setGraphOptions([]);
      return;
    }

    setGraphLoading(true);
    void listGraphsPage(projectId, { limit: 500, offset: 0 })
      .then((payload) => {
        const next = payload.items.filter(
          (item): item is ManagementGraph =>
            typeof item.graph_id === "string" &&
            item.graph_id.trim().length > 0,
        );
        setGraphOptions(next);
      })
      .catch(() => setGraphOptions([]))
      .finally(() => setGraphLoading(false));
  }, [projectId]);

  useEffect(() => {
    if (sortedGraphOptions.length === 0) {
      return;
    }
    if (
      graphId.trim() &&
      sortedGraphOptions.some((item) => item.graph_id === graphId.trim())
    ) {
      return;
    }
    setGraphId(sortedGraphOptions[0].graph_id);
  }, [graphId, sortedGraphOptions]);

  useEffect(() => {
    let cancelled = false;

    async function loadRuntime() {
      setRuntimeLoading(true);
      setRuntimeError(null);
      try {
        const [modelsResponse, toolsResponse] = await Promise.all([
          listRuntimeModels().catch(() => null),
          listRuntimeTools().catch(() => null),
        ]);
        if (cancelled) {
          return;
        }
        setRuntimeModels(modelsResponse?.models || []);
        setRuntimeTools(toolsResponse?.tools || []);
      } catch (loadError) {
        if (!cancelled) {
          setRuntimeError(
            loadError instanceof Error
              ? loadError.message
              : "Failed to load runtime capabilities",
          );
          setRuntimeModels([]);
          setRuntimeTools([]);
        }
      } finally {
        if (!cancelled) {
          setRuntimeLoading(false);
        }
      }
    }

    void loadRuntime();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!graphId.trim()) {
      setSchema(null);
      setSchemaError(null);
      return;
    }

    setSchemaLoading(true);
    setSchemaError(null);
    void getAssistantParameterSchema(graphId.trim(), projectId || undefined)
      .then((payload) => setSchema(payload))
      .catch((schemaLoadError) => {
        setSchema(null);
        setSchemaError(
          schemaLoadError instanceof Error
            ? schemaLoadError.message
            : "Failed to load parameter schema",
        );
      })
      .finally(() => setSchemaLoading(false));
  }, [graphId, projectId]);

  useEffect(() => {
    try {
      setConfigFields(
        buildAssistantConfigFieldValues(config, configPropertyDefs),
      );
    } catch {
      setConfigFields({});
    }
  }, [config, configPropertyDefs]);

  if (!projectId) {
    return (
      <PlatformPage>
        <PageHeader
          actions={
            <PageActions>
              <Button asChild variant="ghost">
                <Link href="/workspace/projects">Open projects</Link>
              </Button>
            </PageActions>
          }
          description="创建助手前必须先确定项目上下文，不然整条能力链都是悬空的。"
          eyebrow="Workspace"
          title="Create Assistant"
        />
        <EmptyState
          description="请先到 Projects 页面选择当前项目，或者在顶部项目选择器里完成切换。"
          title="No project selected"
        />
      </PlatformPage>
    );
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || !graphId.trim()) {
      setError("Name and graph ID are required");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const payload = buildCreateAssistantPayload({
        assistantId,
        config,
        context,
        description,
        graphId,
        metadata,
        name,
        runtimeEnableTools,
        runtimeModelId,
        runtimeToolNames,
      });
      const created = await createAssistant(projectId, payload);
      router.replace(`/workspace/assistants/${created.id}`);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to create assistant",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button asChild variant="ghost">
              <Link href="/workspace/assistants">Back to assistants</Link>
            </Button>
            <Button
              disabled={submitting}
              form={FORM_ID}
              type="submit"
              variant="primary"
            >
              {submitting ? "Creating..." : "Create assistant"}
            </Button>
          </PageActions>
        }
        description="助手创建页保留 schema 驱动参数、runtime 选择和原始 JSON 编辑，保证平台味道别丢。"
        eyebrow="Workspace"
        title="Create Assistant"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Current Project
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {currentProject?.name || "Unknown"}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Graphs
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {sortedGraphOptions.length}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Runtime Models
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {runtimeModels.length}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Runtime Tools
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {runtimeTools.length}
          </div>
        </Card>
      </section>

      {error ? <StateBanner message={error} variant="error" /> : null}
      {runtimeError ? <StateBanner message={runtimeError} /> : null}

      <form className="flex flex-col gap-6" id={FORM_ID} onSubmit={onSubmit}>
        <FormSection
          description="基础资料决定这个助手在当前项目里的身份和挂载目标。"
          title="Assistant Profile"
        >
          <div className="grid gap-5 lg:grid-cols-2">
            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Graph ID
              <Select
                disabled={
                  submitting || graphLoading || sortedGraphOptions.length === 0
                }
                required
                value={graphId}
                onChange={(event) => setGraphId(event.target.value)}
              >
                {sortedGraphOptions.length === 0 ? (
                  <option value="">
                    {graphLoading ? "Loading graphs..." : "No graph available"}
                  </option>
                ) : (
                  sortedGraphOptions.map((option) => (
                    <option key={option.graph_id} value={option.graph_id}>
                      {option.description?.trim()
                        ? `${option.graph_id} - ${option.description}`
                        : option.graph_id}
                    </option>
                  ))
                )}
              </Select>
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Assistant name
              <Input
                disabled={submitting}
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)] lg:col-span-2">
              Description
              <Textarea
                disabled={submitting}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)] lg:col-span-2">
              Optional assistant ID
              <Input
                disabled={submitting}
                placeholder="If empty, upstream runtime generates one"
                value={assistantId}
                onChange={(event) => setAssistantId(event.target.value)}
              />
            </label>
          </div>
        </FormSection>

        <FormSection
          description="runtime 相关选择会写入 config.configurable，不跟 schema 字段混在一起。"
          title="Runtime Configuration"
        >
          <div className="grid gap-5 lg:grid-cols-2">
            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Model group
              <Select
                disabled={submitting || runtimeLoading}
                value={runtimeModelId}
                onChange={(event) => setRuntimeModelId(event.target.value)}
              >
                <option value="">Use runtime default</option>
                {runtimeModels.map((item) => (
                  <option key={item.model_id} value={item.model_id}>
                    {item.display_name}
                    {item.is_default ? " (default)" : ""}
                  </option>
                ))}
              </Select>
            </label>

            <label
              className="flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm text-[var(--foreground)]"
              style={{ borderColor: "var(--border)" }}
            >
              <input
                checked={runtimeEnableTools}
                disabled={submitting}
                style={{ accentColor: "var(--primary)" }}
                type="checkbox"
                onChange={(event) =>
                  setRuntimeEnableTools(event.target.checked)
                }
              />
              Enable tools for this assistant
            </label>
          </div>

          <div
            className="mt-5 rounded-2xl border p-4"
            style={{ borderColor: "var(--border)" }}
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm font-medium text-[var(--foreground)]">
                Tool selection
              </div>
              <PageActions>
                <Button
                  disabled={
                    submitting ||
                    !runtimeEnableTools ||
                    runtimeTools.length === 0
                  }
                  size="sm"
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    setRuntimeToolNames(
                      runtimeTools
                        .map((tool) => tool.name)
                        .filter((toolName) => toolName.trim().length > 0),
                    )
                  }
                >
                  Select all
                </Button>
                <Button
                  disabled={submitting || runtimeToolNames.length === 0}
                  size="sm"
                  type="button"
                  variant="ghost"
                  onClick={() => setRuntimeToolNames([])}
                >
                  Clear
                </Button>
              </PageActions>
            </div>

            <div className="grid max-h-72 gap-2 overflow-auto pr-2">
              {runtimeTools.length === 0 ? (
                <div className="text-sm text-[var(--muted-foreground)]">
                  No tools reported by runtime.
                </div>
              ) : (
                runtimeTools.map((tool) => {
                  const checked = runtimeToolNames.includes(tool.name);
                  return (
                    <label
                      key={tool.name}
                      className="flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <input
                        checked={checked}
                        disabled={submitting || !runtimeEnableTools}
                        style={{ accentColor: "var(--primary)" }}
                        type="checkbox"
                        onChange={() => {
                          setRuntimeToolNames((prev) => {
                            if (prev.includes(tool.name)) {
                              return prev.filter((item) => item !== tool.name);
                            }
                            return [...prev, tool.name];
                          });
                        }}
                      />
                      <div>
                        <div className="font-mono text-sm text-[var(--foreground)]">
                          {tool.name}
                        </div>
                        <div className="text-xs text-[var(--muted-foreground)]">
                          {tool.source || "runtime"} ·{" "}
                          {tool.description || "No description"}
                        </div>
                      </div>
                    </label>
                  );
                })
              )}
            </div>
          </div>
        </FormSection>

        <FormSection
          description="schema 驱动字段和原始 JSON 同时保留，方便从旧平台迁过来的复杂助手继续落地。"
          title="Assistant Parameters"
        >
          <div className="grid gap-5">
            <div
              className="rounded-2xl border px-4 py-4 text-sm text-[var(--muted-foreground)]"
              style={{ borderColor: "var(--border)" }}
            >
              Schema: graph={schema?.graph_id || graphId.trim() || "-"} ·
              version={schema?.schema_version || "v1"}
              {schemaLoading ? " · loading..." : ""}
              {schemaError ? ` · ${schemaError}` : ""}
            </div>

            {configPropertyDefs.length > 0 ? (
              <div className="grid gap-5 lg:grid-cols-2">
                {configPropertyDefs.map((field) => (
                  <label
                    key={field.key}
                    className="grid gap-2 text-sm font-medium text-[var(--foreground)]"
                  >
                    {field.key}
                    {field.type === "boolean" ? (
                      <Select
                        disabled={submitting}
                        required={field.required}
                        value={configFields[field.key] ?? ""}
                        onChange={(event) => {
                          try {
                            setConfigFields((prev) => ({
                              ...prev,
                              [field.key]: event.target.value,
                            }));
                            setConfig(
                              applyAssistantConfigFieldValue(
                                config,
                                field.key,
                                event.target.value,
                                field.type,
                              ),
                            );
                            setError(null);
                          } catch (fieldError) {
                            setError(
                              fieldError instanceof Error
                                ? fieldError.message
                                : "Failed to update config field",
                            );
                          }
                        }}
                      >
                        <option value="">Unset</option>
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </Select>
                    ) : (
                      <Input
                        disabled={submitting}
                        placeholder={field.type}
                        required={field.required}
                        value={configFields[field.key] ?? ""}
                        onChange={(event) => {
                          try {
                            setConfigFields((prev) => ({
                              ...prev,
                              [field.key]: event.target.value,
                            }));
                            setConfig(
                              applyAssistantConfigFieldValue(
                                config,
                                field.key,
                                event.target.value,
                                field.type,
                              ),
                            );
                            setError(null);
                          } catch (fieldError) {
                            setError(
                              fieldError instanceof Error
                                ? fieldError.message
                                : "Failed to update config field",
                            );
                          }
                        }}
                      />
                    )}
                  </label>
                ))}
              </div>
            ) : null}

            <div className="grid gap-5 xl:grid-cols-3">
              <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                Config (JSON object)
                <Textarea
                  className="font-mono text-xs leading-6"
                  disabled={submitting}
                  value={config}
                  onChange={(event) => setConfig(event.target.value)}
                />
              </label>

              <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                Context (JSON object)
                <Textarea
                  className="font-mono text-xs leading-6"
                  disabled={submitting}
                  value={context}
                  onChange={(event) => setContext(event.target.value)}
                />
              </label>

              <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                Metadata (JSON object)
                <Textarea
                  className="font-mono text-xs leading-6"
                  disabled={submitting}
                  value={metadata}
                  onChange={(event) => setMetadata(event.target.value)}
                />
              </label>
            </div>
          </div>
        </FormSection>
      </form>

      <FormSection
        description="请求体预览能帮你快速确认 graph、config、context 和 metadata 最终会长成什么样。"
        title="Request Preview"
      >
        {requestPreview.error ? (
          <StateBanner message={requestPreview.error} variant="error" />
        ) : (
          <pre
            className="overflow-auto rounded-2xl border p-4 text-xs leading-6"
            style={{
              borderColor: "var(--border)",
              background: "var(--surface-soft)",
            }}
          >
            {JSON.stringify(requestPreview.payload, null, 2)}
          </pre>
        )}
      </FormSection>
    </PlatformPage>
  );
}
