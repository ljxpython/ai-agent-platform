"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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
import { StatusPill } from "@/components/platform/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  getAssistant,
  getAssistantParameterSchema,
  resyncAssistant,
  updateAssistant,
  type AssistantParameterSchema,
  type ManagementAssistant,
} from "@/lib/management-api/assistants";
import {
  buildChatHref,
  writeRecentChatTarget,
} from "@/lib/chat-target-preference";
import { parseJsonObject, stringifyJsonObject } from "@/lib/json-object";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

const FORM_ID = "assistant-detail-form";

export default function AssistantDetailPage() {
  const params = useParams<{ assistantId: string }>();
  const router = useRouter();
  const { projectId } = useWorkspaceContext();
  const assistantId = String(params.assistantId || "");

  const [item, setItem] = useState<ManagementAssistant | null>(null);
  const [schema, setSchema] = useState<AssistantParameterSchema | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resyncing, setResyncing] = useState(false);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editGraphId, setEditGraphId] = useState("");
  const [editStatus, setEditStatus] = useState<"active" | "disabled">("active");
  const [editConfig, setEditConfig] = useState("{}");
  const [editContext, setEditContext] = useState("{}");
  const [editMetadata, setEditMetadata] = useState("{}");
  const [configFields, setConfigFields] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!assistantId) {
      return;
    }

    setLoading(true);
    setError(null);
    setNotice(null);
    void getAssistant(assistantId, projectId || undefined)
      .then((payload) => {
        setItem(payload);
        setEditName(payload.name);
        setEditDescription(payload.description || "");
        setEditGraphId(payload.graph_id);
        setEditStatus(payload.status === "disabled" ? "disabled" : "active");
        setEditConfig(stringifyJsonObject(payload.config));
        setEditContext(stringifyJsonObject(payload.context));
        setEditMetadata(stringifyJsonObject(payload.metadata));
      })
      .catch((loadError) =>
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Failed to load assistant",
        ),
      )
      .finally(() => setLoading(false));
  }, [assistantId, projectId]);

  useEffect(() => {
    if (!editGraphId.trim()) {
      setSchema(null);
      return;
    }

    setSchemaLoading(true);
    void getAssistantParameterSchema(editGraphId.trim(), projectId || undefined)
      .then((payload) => setSchema(payload))
      .catch(() => setSchema(null))
      .finally(() => setSchemaLoading(false));
  }, [editGraphId, projectId]);

  const configPropertyDefs = useMemo(
    () => getAssistantConfigFields(schema),
    [schema],
  );

  useEffect(() => {
    try {
      setConfigFields(
        buildAssistantConfigFieldValues(editConfig, configPropertyDefs),
      );
    } catch {
      setConfigFields({});
    }
  }, [configPropertyDefs, editConfig]);

  async function onSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assistantId) {
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateAssistant(
        assistantId,
        {
          name: editName.trim(),
          description: editDescription.trim(),
          graph_id: editGraphId.trim(),
          status: editStatus,
          config: parseJsonObject(editConfig, "config"),
          context: parseJsonObject(editContext, "context"),
          metadata: parseJsonObject(editMetadata, "metadata"),
        },
        projectId || undefined,
      );
      setItem(updated);
      setNotice("Assistant updated");
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Failed to update assistant",
      );
    } finally {
      setSaving(false);
    }
  }

  async function onResync() {
    if (!assistantId) {
      return;
    }

    setResyncing(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await resyncAssistant(
        assistantId,
        projectId || undefined,
      );
      setItem(updated);
      setEditName(updated.name);
      setEditDescription(updated.description || "");
      setEditGraphId(updated.graph_id);
      setEditStatus(updated.status === "disabled" ? "disabled" : "active");
      setEditConfig(stringifyJsonObject(updated.config));
      setEditContext(stringifyJsonObject(updated.context));
      setEditMetadata(stringifyJsonObject(updated.metadata));
      setNotice("Assistant resynced");
    } catch (resyncError) {
      setError(
        resyncError instanceof Error
          ? resyncError.message
          : "Failed to resync assistant",
      );
    } finally {
      setResyncing(false);
    }
  }

  if (!loading && !item && !error) {
    return (
      <PlatformPage>
        <PageHeader
          actions={
            <PageActions>
              <Button asChild variant="ghost">
                <Link href="/workspace/assistants">Back to assistants</Link>
              </Button>
            </PageActions>
          }
          description="当前助手没有读取到详情。"
          eyebrow="Workspace"
          title="Assistant Detail"
        />
        <EmptyState
          description="请返回助手列表重新选择一个可访问助手。"
          title="Assistant not found"
        />
      </PlatformPage>
    );
  }

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button asChild variant="ghost">
              <Link href="/workspace/assistants">Back to assistants</Link>
            </Button>
            {item ? (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  const target = {
                    targetType: "assistant" as const,
                    assistantId: item.langgraph_assistant_id || assistantId,
                  };
                  if (projectId) {
                    writeRecentChatTarget(projectId, target);
                  }
                  router.push(
                    buildChatHref({
                      projectId,
                      target,
                    }),
                  );
                }}
              >
                Open in chat
              </Button>
            ) : null}
            <Button
              disabled={!item || resyncing}
              type="button"
              variant="ghost"
              onClick={() => void onResync()}
            >
              {resyncing ? "Resyncing..." : "Resync"}
            </Button>
            <Button
              disabled={!item || saving}
              form={FORM_ID}
              type="submit"
              variant="primary"
            >
              {saving ? "Saving..." : "Save changes"}
            </Button>
          </PageActions>
        }
        description="助手详情页保留 graph、schema、sync 和原始配置编辑，不把平台核心能力阉割成一层假皮。"
        eyebrow="Workspace"
        title={item?.name || "Assistant Detail"}
      />

      {loading ? <StateBanner message="Loading assistant detail..." /> : null}
      {error ? <StateBanner message={error} variant="error" /> : null}
      {notice ? <StateBanner message={notice} variant="success" /> : null}

      {item ? (
        <>
          <section className="grid gap-4 xl:grid-cols-4">
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Status
              </div>
              <div className="mt-4">
                <StatusPill
                  label={item.status}
                  variant={item.status === "active" ? "success" : "warning"}
                />
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Sync
              </div>
              <div className="mt-4">
                <StatusPill
                  label={item.sync_status || "unknown"}
                  variant={
                    item.sync_status === "ready" ||
                    item.sync_status === "synced"
                      ? "success"
                      : item.sync_status === "failed"
                        ? "danger"
                        : "warning"
                  }
                />
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Graph
              </div>
              <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
                {item.graph_id}
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Last Synced
              </div>
              <div className="mt-4 text-sm leading-7 text-[var(--muted-foreground)]">
                {item.last_synced_at
                  ? new Date(item.last_synced_at).toLocaleString()
                  : "-"}
              </div>
            </Card>
          </section>

          <form className="flex flex-col gap-6" id={FORM_ID} onSubmit={onSave}>
            <FormSection
              description="基础资料和同步元信息放在一起看，出问题时不用到处翻。"
              title="Assistant Profile"
            >
              <div className="grid gap-5 lg:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                  Name
                  <Input
                    disabled={saving}
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                  />
                </label>

                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                  Status
                  <Select
                    disabled={saving}
                    value={editStatus}
                    onChange={(event) =>
                      setEditStatus(
                        event.target.value === "disabled"
                          ? "disabled"
                          : "active",
                      )
                    }
                  >
                    <option value="active">active</option>
                    <option value="disabled">disabled</option>
                  </Select>
                </label>

                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)] lg:col-span-2">
                  Description
                  <Textarea
                    disabled={saving}
                    value={editDescription}
                    onChange={(event) => setEditDescription(event.target.value)}
                  />
                </label>

                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                  Graph ID
                  <Input
                    disabled={saving}
                    value={editGraphId}
                    onChange={(event) => setEditGraphId(event.target.value)}
                  />
                </label>

                <div className="grid gap-2 text-sm text-[var(--muted-foreground)]">
                  <p>Assistant ID: {item.id}</p>
                  <p>LangGraph Assistant ID: {item.langgraph_assistant_id}</p>
                  <p>Runtime Base URL: {item.runtime_base_url || "-"}</p>
                  <p>Last sync error: {item.last_sync_error || "-"}</p>
                </div>
              </div>
            </FormSection>

            <FormSection
              description="schema 驱动字段继续保留，避免配置被粗暴降级成只剩几个文本框。"
              title="Parameters"
            >
              <div className="grid gap-5">
                <div
                  className="rounded-2xl border px-4 py-4 text-sm text-[var(--muted-foreground)]"
                  style={{ borderColor: "var(--border)" }}
                >
                  Schema: graph={schema?.graph_id || editGraphId.trim() || "-"}{" "}
                  · version={schema?.schema_version || "v1"}
                  {schemaLoading ? " · loading..." : ""}
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
                            disabled={saving}
                            required={field.required}
                            value={configFields[field.key] ?? ""}
                            onChange={(event) => {
                              try {
                                setConfigFields((prev) => ({
                                  ...prev,
                                  [field.key]: event.target.value,
                                }));
                                setEditConfig(
                                  applyAssistantConfigFieldValue(
                                    editConfig,
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
                            disabled={saving}
                            placeholder={field.type}
                            required={field.required}
                            value={configFields[field.key] ?? ""}
                            onChange={(event) => {
                              try {
                                setConfigFields((prev) => ({
                                  ...prev,
                                  [field.key]: event.target.value,
                                }));
                                setEditConfig(
                                  applyAssistantConfigFieldValue(
                                    editConfig,
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
                      disabled={saving}
                      value={editConfig}
                      onChange={(event) => setEditConfig(event.target.value)}
                    />
                  </label>

                  <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                    Context (JSON object)
                    <Textarea
                      className="font-mono text-xs leading-6"
                      disabled={saving}
                      value={editContext}
                      onChange={(event) => setEditContext(event.target.value)}
                    />
                  </label>

                  <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                    Metadata (JSON object)
                    <Textarea
                      className="font-mono text-xs leading-6"
                      disabled={saving}
                      value={editMetadata}
                      onChange={(event) => setEditMetadata(event.target.value)}
                    />
                  </label>
                </div>
              </div>
            </FormSection>
          </form>
        </>
      ) : null}
    </PlatformPage>
  );
}
