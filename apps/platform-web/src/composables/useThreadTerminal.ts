import { onBeforeUnmount, ref, watch, type Ref } from 'vue';
import type { TerminalSession } from '@/types/workspace';
import {
  closeTerminalSession,
  createTerminalSession,
  getTerminalOutput,
  listTerminalSessions,
  resizeTerminal,
  sendTerminalInput,
} from '@/services/threads/terminal.service';

export interface TerminalOutputChunk {
  terminalId: string;
  data: Uint8Array;
  text: string;
  truncated: boolean;
}

export function useThreadTerminal(
  projectId: Ref<string>,
  threadId: Ref<string>,
  options: {
    onOutputChunk?: (chunk: TerminalOutputChunk) => void;
    onSessionExited?: (session: TerminalSession) => void;
  } = {},
) {
  const sessions = ref<TerminalSession[]>([]);
  const activeTerminalId = ref<string>('');
  const loading = ref(false);
  const creating = ref(false);
  const error = ref<string | null>(null);

  // 会话状态维护
  const sessionOffsets = new Map<string, number>();
  const sessionDecoders = new Map<string, TextDecoder>();
  const pendingInputBuffers = new Map<string, Uint8Array>();
  const inFlightInput = new Map<string, boolean>();
  const retryCountMap = new Map<string, number>();

  let pollingTimer: ReturnType<typeof setTimeout> | null = null;
  let isBackground = false;
  let disposed = false;

  function getDecoder(id: string): TextDecoder {
    let dec = sessionDecoders.get(id);
    if (!dec) {
      dec = new TextDecoder('utf-8');
      sessionDecoders.set(id, dec);
    }
    return dec;
  }

  // 刷新会话列表
  async function refreshSessions() {
    if (!projectId.value || !threadId.value || disposed) return;
    loading.value = true;
    try {
      const resp = await listTerminalSessions(
        projectId.value,
        threadId.value,
      );
      sessions.value = resp.items;
      if (!activeTerminalId.value && resp.items.length > 0) {
        activeTerminalId.value = resp.items[0].terminal_id;
      }
    } catch (err: unknown) {
      console.warn('获取终端列表失败:', err);
    } finally {
      loading.value = false;
    }
  }

  // 创建新终端
  async function createSession(rows = 24, cols = 80): Promise<TerminalSession | null> {
    if (!projectId.value || !threadId.value || disposed) return null;
    creating.value = true;
    error.value = null;
    try {
      const requestId = crypto.randomUUID();
      const session = await createTerminalSession(
        projectId.value,
        threadId.value,
        {
          request_id: requestId,
          acknowledge_execution: true,
          rows,
          cols,
        },
      );
      sessions.value = [...sessions.value, session];
      activeTerminalId.value = session.terminal_id;
      sessionOffsets.set(session.terminal_id, 0);
      return session;
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '创建终端失败';
      return null;
    } finally {
      creating.value = false;
    }
  }

  // 关闭指定终端
  async function closeSession(terminalId: string) {
    if (!projectId.value || !threadId.value) return;
    try {
      await closeTerminalSession(
        projectId.value,
        threadId.value,
        terminalId,
      );
    } catch (err) {
      console.warn('关闭终端失败:', err);
    } finally {
      sessions.value = sessions.value.filter((s) => s.terminal_id !== terminalId);
      sessionOffsets.delete(terminalId);
      sessionDecoders.delete(terminalId);
      pendingInputBuffers.delete(terminalId);
      inFlightInput.delete(terminalId);
      retryCountMap.delete(terminalId);

      if (activeTerminalId.value === terminalId) {
        activeTerminalId.value = sessions.value[0]?.terminal_id || '';
      }
    }
  }

  function concatBytes(a: Uint8Array, b: Uint8Array): Uint8Array {
    const res = new Uint8Array(a.length + b.length);
    res.set(a, 0);
    res.set(b, a.length);
    return res;
  }

  function bytesToBase64(bytes: Uint8Array): string {
    let binaryStr = '';
    for (let i = 0; i < bytes.length; i++) {
      binaryStr += String.fromCharCode(bytes[i]);
    }
    return btoa(binaryStr);
  }

  // 输入发送入口（带批处理合并缓冲池）
  async function sendInput(terminalId: string, textOrBytes: string | Uint8Array) {
    if (!projectId.value || !threadId.value || disposed) return;

    let rawBytes: Uint8Array;
    if (typeof textOrBytes === 'string') {
      rawBytes = new TextEncoder().encode(textOrBytes);
    } else {
      rawBytes = textOrBytes;
    }

    if (rawBytes.length === 0) return;

    const session = sessions.value.find((s) => s.terminal_id === terminalId);
    if (!session || session.status === 'exited') return;

    // 追加到待发送缓冲池
    const existing = pendingInputBuffers.get(terminalId);
    if (existing && existing.length > 0) {
      pendingInputBuffers.set(terminalId, concatBytes(existing, rawBytes));
    } else {
      pendingInputBuffers.set(terminalId, rawBytes);
    }

    void flushInputBuffer(terminalId);
  }

  async function flushInputBuffer(terminalId: string) {
    if (inFlightInput.get(terminalId) || disposed) return;

    const pending = pendingInputBuffers.get(terminalId);
    if (!pending || pending.length === 0) return;

    const session = sessions.value.find((s) => s.terminal_id === terminalId);
    if (!session || session.status === 'exited') {
      pendingInputBuffers.delete(terminalId);
      return;
    }

    // 从缓冲池提取本批次并清空
    pendingInputBuffers.delete(terminalId);
    inFlightInput.set(terminalId, true);

    const b64 = bytesToBase64(pending);
    const seq = session.next_input_sequence;

    try {
      const ack = await sendTerminalInput(
        projectId.value,
        threadId.value,
        terminalId,
        {
          sequence: seq,
          data_base64: b64,
        },
      );

      // 请求成功，重置重试计数
      retryCountMap.set(terminalId, 0);

      // 更新最新序列号
      session.next_input_sequence = ack.next_input_sequence;

      // 如果后端只接收了部分字节，将未消费的字节插回缓冲区头部
      if (ack.accepted_bytes < pending.length) {
        const remaining = pending.subarray(ack.accepted_bytes);
        const currentPending = pendingInputBuffers.get(terminalId);
        if (currentPending && currentPending.length > 0) {
          pendingInputBuffers.set(terminalId, concatBytes(remaining, currentPending));
        } else {
          pendingInputBuffers.set(terminalId, remaining);
        }
      }
    } catch (err: unknown) {
      console.warn('终端输入发送异常:', err);
      const httpError = err as { response?: { status?: number; data?: { code?: string } } };
      const status = httpError?.response?.status;
      const code = httpError?.response?.data?.code;

      if (status === 409) {
        if (code === 'terminal_exited') {
          session.status = 'exited';
          pendingInputBuffers.delete(terminalId);
        } else if (code === 'terminal_input_sequence' || code === 'terminal_input_conflict') {
          const retries = (retryCountMap.get(terminalId) || 0) + 1;
          retryCountMap.set(terminalId, retries);
          if (retries <= 3) {
            const currentPending = pendingInputBuffers.get(terminalId);
            pendingInputBuffers.set(
              terminalId,
              currentPending ? concatBytes(pending, currentPending) : pending,
            );
          } else {
            console.error(`终端 ${terminalId} 序号冲突超出重试上限，丢弃冲突缓冲`);
            pendingInputBuffers.delete(terminalId);
            retryCountMap.set(terminalId, 0);
          }
        }
      } else {
        const retries = (retryCountMap.get(terminalId) || 0) + 1;
        retryCountMap.set(terminalId, retries);
        if (retries <= 2) {
          const currentPending = pendingInputBuffers.get(terminalId);
          pendingInputBuffers.set(
            terminalId,
            currentPending ? concatBytes(pending, currentPending) : pending,
          );
        } else {
          pendingInputBuffers.delete(terminalId);
          retryCountMap.set(terminalId, 0);
        }
      }
    } finally {
      inFlightInput.set(terminalId, false);
      const remaining = pendingInputBuffers.get(terminalId);
      if (remaining && remaining.length > 0) {
        setTimeout(() => {
          void flushInputBuffer(terminalId);
        }, 50);
      }
    }
  }

  // 调整尺寸防抖
  let resizeDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  function handleResize(terminalId: string, rows: number, cols: number) {
    if (!projectId.value || !threadId.value) return;
    if (resizeDebounceTimer) clearTimeout(resizeDebounceTimer);

    resizeDebounceTimer = setTimeout(async () => {
      try {
        await resizeTerminal(
          projectId.value,
          threadId.value,
          terminalId,
          { rows, cols },
        );
      } catch (err) {
        console.warn('调整终端尺寸失败:', err);
      }
    }, 200);
  }

  // 轮询输出单步
  async function pollOutputStep() {
    if (disposed || !projectId.value || !threadId.value) return;

    const currentSessions = [...sessions.value];
    for (const session of currentSessions) {
      const termId = session.terminal_id;
      const currentOffset = sessionOffsets.get(termId) || 0;

      // 如果已退出且已读到 end_offset，则不继续读
      if (session.status === 'exited' && currentOffset >= session.end_offset) {
        continue;
      }

      try {
        const out = await getTerminalOutput(
          projectId.value,
          threadId.value,
          termId,
          currentOffset,
        );

        sessionOffsets.set(termId, out.next_offset);

        // 更新 session 状态
        session.status = out.status;
        session.exit_code = out.exit_code;
        session.reason = out.reason;
        session.next_input_sequence = out.next_input_sequence;
        session.end_offset = out.end_offset;

        if (out.data_base64) {
          const binaryStr = atob(out.data_base64);
          const bytes = new Uint8Array(binaryStr.length);
          for (let i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
          }
          const text = getDecoder(termId).decode(bytes, { stream: true });

          options.onOutputChunk?.({
            terminalId: termId,
            data: bytes,
            text,
            truncated: out.truncated,
          });
        }

        if (out.status === 'exited' && out.next_offset >= out.end_offset) {
          options.onSessionExited?.(out);
        }
      } catch (err: unknown) {
        // 409 或 404 等可能已关闭
        console.warn(`读取终端 ${termId} 输出失败:`, err);
      }
    }
  }

  function scheduleNextPoll() {
    if (disposed) return;
    const interval = isBackground ? 2500 : 350;
    pollingTimer = setTimeout(async () => {
      await pollOutputStep();
      scheduleNextPoll();
    }, interval);
  }

  // 设置前后台状态
  function setBackground(val: boolean) {
    isBackground = val;
  }

  // 监听线程切换
  watch(
    [projectId, threadId],
    ([newProject, newThread], [oldProject, oldThread]) => {
      if (newProject !== oldProject || newThread !== oldThread) {
        sessions.value = [];
        activeTerminalId.value = '';
        sessionOffsets.clear();
        sessionDecoders.clear();
        pendingInputBuffers.clear();
        inFlightInput.clear();
        retryCountMap.clear();

        if (newProject && newThread) {
          void refreshSessions();
        }
      }
    },
    { immediate: true },
  );

  // 启动轮询
  scheduleNextPoll();

  onBeforeUnmount(() => {
    disposed = true;
    if (pollingTimer) clearTimeout(pollingTimer);
    if (resizeDebounceTimer) clearTimeout(resizeDebounceTimer);
  });

  return {
    sessions,
    activeTerminalId,
    loading,
    creating,
    error,
    refreshSessions,
    createSession,
    closeSession,
    sendInput,
    handleResize,
    setBackground,
  };
}
