import { cancelRuntimeRun, normalizeRuntimeGatewayError } from '@/services/runtime-gateway/workspace.service'
import { buildChatRunSubmitOptions } from '@/services/runtime/runtime-contract'
import type { PlatformChatStreamActionDeps } from './types'
import {
  buildOptimisticMessage,
  createThreadMetadata,
  getMetadataCheckpointId,
  hasPendingTaskToolCall,
  toOptimisticBaseMessage
} from './helpers'

export function createPlatformChatStreamActions(deps: PlatformChatStreamActionDeps) {
  function clearDetailFeedback(controlOptions: { preserveInfo?: boolean } = {}) {
    deps.detailError.value = ''

    if (!controlOptions.preserveInfo) {
      deps.detailInfo.value = ''
    }
  }

  function switchThread(threadId: string | null) {
    deps.stream.switchThread(threadId)
  }

  function resetStreamView(controlOptions: { preserveInfo?: boolean } = {}) {
    deps.options.historyItems.value = []
    deps.options.selectedBranch.value = ''
    deps.stream.switchThread(null)
    clearDetailFeedback(controlOptions)
    deps.sending.value = false
    deps.cancelling.value = false
    deps.lastRunId.value = ''
    deps.currentRunId.value = ''
    deps.lastEventAt.value = ''
  }

  async function sendMessage(content: string, attachments: Parameters<typeof buildOptimisticMessage>[1] = []) {
    const projectId = deps.options.projectId.value.trim()
    const target = deps.options.target.value
    const normalizedContent = content.trim()
    const normalizedAttachments = attachments.filter((item) => item && typeof item === 'object')

    if (!projectId || !target || deps.sending.value || (!normalizedContent && normalizedAttachments.length === 0)) {
      return false
    }

    deps.sending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    deps.lastRunId.value = ''

    const humanMessage = buildOptimisticMessage(content, normalizedAttachments)
    const checkpointId =
      deps.options.selectedBranch.value && deps.stream.branch.value
        ? getMetadataCheckpointId(deps.messageMetadataById.value[deps.messages.value[deps.messages.value.length - 1]?.id || ''])
        : ''
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.submit(
        {
          messages: [humanMessage]
        },
        {
          metadata: !deps.options.activeThreadId.value.trim() ? createThreadMetadata(target) : undefined,
          checkpoint:
            checkpointId && deps.options.historyItems.value.length > 0
              ? { checkpoint_id: checkpointId }
              : undefined,
          optimisticValues: (prev: Record<string, unknown>) => ({
            ...prev,
            messages: [...((prev.messages as unknown[] | undefined) || []), humanMessage]
          }),
          ...runtimeSubmitOptions,
          ...(deps.options.runOptions.debugMode ? { interruptBefore: ['tools'] } : {}),
          streamSubgraphs: true,
          multitaskStrategy: 'interrupt',
          onError: (submitError: unknown) => {
            deps.detailError.value = normalizeRuntimeGatewayError(submitError, '对话发送失败').message
          }
        }
      )
      return true
    } catch (runError) {
      deps.detailError.value = normalizeRuntimeGatewayError(runError, '对话发送失败').message
      deps.sending.value = false
      deps.cancelling.value = false
      deps.currentRunId.value = ''
      return false
    }
  }

  async function continueDebugRun() {
    const threadId = deps.options.activeThreadId.value.trim()
    if (!threadId || deps.sending.value) {
      return false
    }

    deps.sending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()

    const pendingTaskToolCall = hasPendingTaskToolCall(deps.stream.messages.value)
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.submit(undefined, {
        ...runtimeSubmitOptions,
        ...(pendingTaskToolCall ? { interruptAfter: ['tools'] } : { interruptBefore: ['tools'] }),
        streamSubgraphs: true,
        multitaskStrategy: 'interrupt'
      })
      return true
    } catch (runError) {
      deps.detailError.value = normalizeRuntimeGatewayError(runError, '运行继续失败').message
      deps.sending.value = false
      deps.cancelling.value = false
      deps.currentRunId.value = ''
      return false
    }
  }

  async function cancelActiveRun() {
    const projectId = deps.options.projectId.value.trim()
    const threadId = deps.options.activeThreadId.value.trim()

    if (!deps.sending.value || !projectId || !threadId) {
      return false
    }

    deps.cancelling.value = true

    try {
      if (deps.currentRunId.value.trim()) {
        await cancelRuntimeRun(projectId, threadId, deps.currentRunId.value)
      }
    } catch {
      // 服务端取消失败时，仍然中止当前前端流，避免页面继续假死。
    } finally {
      deps.stream.stop()
    }

    return true
  }

  async function resumeInterruptedRun(resumePayload: unknown) {
    const threadId = deps.options.activeThreadId.value.trim()
    if (!threadId || deps.interruptPayload.value === undefined || deps.sending.value) {
      return false
    }

    deps.sending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.submit(null, {
        command: {
          resume: resumePayload
        },
        ...runtimeSubmitOptions,
        streamSubgraphs: true,
        multitaskStrategy: 'interrupt'
      })
      return true
    } catch (runError) {
      deps.detailError.value = normalizeRuntimeGatewayError(runError, '恢复中断失败').message
      deps.sending.value = false
      deps.cancelling.value = false
      deps.currentRunId.value = ''
      return false
    }
  }

  function selectBranch(branch: string) {
    deps.options.selectedBranch.value = branch.trim()
    deps.detailError.value = ''
    deps.stream.setBranch(deps.options.selectedBranch.value)
  }

  async function retryMessage(messageId: string) {
    const threadId = deps.options.activeThreadId.value.trim()
    const checkpointId = deps.messageMetadataById.value[messageId]?.checkpointId?.trim() || ''

    if (!threadId || !checkpointId || deps.sending.value) {
      return false
    }

    deps.sending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    deps.lastRunId.value = ''
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.submit(undefined, {
        checkpoint: {
          checkpoint_id: checkpointId
        },
        ...runtimeSubmitOptions,
        ...(deps.options.runOptions.debugMode ? { interruptBefore: ['tools'] } : {}),
        streamSubgraphs: true,
        multitaskStrategy: 'interrupt'
      })
      return true
    } catch (runError) {
      deps.detailError.value = normalizeRuntimeGatewayError(runError, '重新执行失败').message
      deps.sending.value = false
      deps.cancelling.value = false
      deps.currentRunId.value = ''
      return false
    }
  }

  async function editHumanMessage(messageId: string, content: Parameters<typeof toOptimisticBaseMessage>[0]) {
    const threadId = deps.options.activeThreadId.value.trim()
    const metadata = deps.messageMetadataById.value[messageId]
    const checkpointId = metadata?.parentCheckpoint?.checkpoint_id?.trim() || ''

    if (!threadId || !checkpointId || deps.sending.value) {
      return false
    }

    const optimisticMessage = toOptimisticBaseMessage(content)

    deps.sending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    deps.lastRunId.value = ''
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.submit(
        {
          messages: [optimisticMessage]
        },
        {
          checkpoint: {
            checkpoint_id: checkpointId
          },
          optimisticValues: (prev: Record<string, unknown>) => ({
            ...prev,
            messages: [...((prev.messages as unknown[] | undefined) || []), optimisticMessage]
          }),
          ...runtimeSubmitOptions,
          ...(deps.options.runOptions.debugMode ? { interruptBefore: ['tools'] } : {}),
          streamSubgraphs: true,
          multitaskStrategy: 'interrupt'
        }
      )
      return true
    } catch (runError) {
      deps.detailError.value = normalizeRuntimeGatewayError(runError, '编辑重发失败').message
      deps.sending.value = false
      deps.cancelling.value = false
      deps.currentRunId.value = ''
      return false
    }
  }

  return {
    cancelActiveRun,
    clearDetailFeedback,
    continueDebugRun,
    editHumanMessage,
    resetStreamView,
    resumeInterruptedRun,
    retryMessage,
    selectBranch,
    sendMessage,
    switchThread
  }
}
