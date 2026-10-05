import { describe, expect, it, vi, beforeEach } from "vitest";
import { computed, ref } from "vue";
import {
  useChatRunConfig,
  clearProjectModelBundleCache,
} from "./useChatRunConfig";
import * as runtimeService from "@/services/runtime/runtime.service";
import * as policyService from "@/services/runtime-policies/runtime-policies.service";

describe("useChatRunConfig", () => {
  beforeEach(() => {
    clearProjectModelBundleCache();
    vi.restoreAllMocks();
  });

  it("loads runtime models and defaults to project policy default", async () => {
    vi.spyOn(runtimeService, "listRuntimeModels").mockResolvedValue({
      models: [
        {
          id: "model-1",
          name: "Model 1",
          display_name: "Model One",
          enabled: true,
          provider: "openai",
          created_at: "",
        },
        {
          id: "model-2",
          name: "Model 2",
          display_name: "Model Two",
          enabled: true,
          provider: "openai",
          created_at: "",
        },
      ],
    });
    vi.spyOn(policyService, "listRuntimeModelPolicies").mockResolvedValue({
      items: [
        {
          catalog_id: "model-2",
          policy: {
            is_enabled: true,
            is_default_for_project: true,
          },
        },
      ],
    });

    const context = ref({ model_id: "" });
    const recursionLimit = ref(100);
    const isModeLocked = computed(() => false);

    const config = useChatRunConfig({
      projectId: "proj-1",
      graphId: "chat",
      context,
      recursionLimit,
      isModeLocked,
    });

    expect(config.modelsLoading.value).toBe(true);

    // Wait for promise resolution
    await vi.waitFor(() => {
      expect(config.modelsLoading.value).toBe(false);
    });

    expect(config.models.value).toHaveLength(2);
    expect(config.defaultModelId.value).toBe("model-2");
    expect(context.value.model_id).toBe("model-2");
  });

  it("manages draft options and applies updates with validation", () => {
    vi.spyOn(runtimeService, "listRuntimeModels").mockResolvedValue({
      models: [],
    });
    vi.spyOn(policyService, "listRuntimeModelPolicies").mockResolvedValue({
      items: [],
    });

    const validUuid = "12345678-1234-1234-1234-123456789abc";
    const context = ref({ model_id: validUuid, execution_mode: "standard" });
    const recursionLimit = ref(50);
    const isModeLocked = computed(() => false);

    const config = useChatRunConfig({
      projectId: "proj-2",
      graphId: "dear_agent",
      context,
      recursionLimit,
      isModeLocked,
    });

    config.openOptions();
    expect(config.optionsOpen.value).toBe(true);
    expect(config.draftRunOptions.modelId).toBe(validUuid);
    expect(config.draftRunOptions.recursionLimit).toBe("50");

    // Invalid recursion limit
    config.draftRunOptions.recursionLimit = "0";
    const ok = config.applyOptions();
    expect(ok).toBe(false);
    expect(config.optionsError.value).toContain("1 到 1000");

    // Valid update
    const updatedUuid = "87654321-4321-4321-4321-cba987654321";
    config.draftRunOptions.recursionLimit = "200";
    config.draftRunOptions.modelId = updatedUuid;
    const ok2 = config.applyOptions();
    expect(ok2).toBe(true);
    expect(recursionLimit.value).toBe(200);
    expect(context.value.model_id).toBe(updatedUuid);
    expect(config.optionsOpen.value).toBe(false);
  });
});
