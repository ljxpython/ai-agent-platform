import { ref, shallowRef } from "vue";
import type { EvidenceDetail } from "../types";

export function useEvidenceLookup() {
  const evidenceMap = shallowRef<Map<string, EvidenceDetail>>(new Map());
  const activeEvidence = ref<EvidenceDetail | null>(null);
  const isEvidenceDrawerOpen = ref(false);

  function registerEvidence(evidence: EvidenceDetail) {
    if (!evidence.evidence_id) return;
    const nextMap = new Map(evidenceMap.value);
    nextMap.set(evidence.evidence_id, evidence);
    evidenceMap.value = nextMap;
  }

  function parseAndIndexToolMessage(content: string): string | null {
    if (!content || typeof content !== "string") return null;
    const trimmed = content.trim();
    if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;

    try {
      const parsed = JSON.parse(trimmed) as Record<string, unknown>;
      if (typeof parsed.evidence_id === "string" && parsed.evidence_id.trim()) {
        const evidence: EvidenceDetail = {
          evidence_id: parsed.evidence_id.trim(),
          operation: (parsed.operation as string) || "internal_query",
          observed_at:
            (parsed.observed_at as string) || new Date().toISOString(),
          scope: parsed.scope as Record<string, unknown> | undefined,
          audit_recorded: Boolean(parsed.audit_recorded),
          data: parsed.data as Record<string, unknown> | undefined,
        };
        registerEvidence(evidence);
        return evidence.evidence_id;
      }
    } catch {
      // 非合法 JSON 则忽略
    }
    return null;
  }

  function openEvidence(evidenceId: string) {
    const found = evidenceMap.value.get(evidenceId);
    if (found) {
      activeEvidence.value = found;
      isEvidenceDrawerOpen.value = true;
    } else {
      activeEvidence.value = {
        evidence_id: evidenceId,
        operation: "unknown",
        observed_at: new Date().toISOString(),
        data: {
          error: "引用未核实：本会话中未检索到该编号的内部工具事实。",
        },
      };
      isEvidenceDrawerOpen.value = true;
    }
  }

  function closeEvidence() {
    isEvidenceDrawerOpen.value = false;
    activeEvidence.value = null;
  }

  function clearAllEvidence() {
    evidenceMap.value = new Map();
    activeEvidence.value = null;
    isEvidenceDrawerOpen.value = false;
  }

  return {
    evidenceMap,
    activeEvidence,
    isEvidenceDrawerOpen,
    registerEvidence,
    parseAndIndexToolMessage,
    openEvidence,
    closeEvidence,
    clearAllEvidence,
  };
}
