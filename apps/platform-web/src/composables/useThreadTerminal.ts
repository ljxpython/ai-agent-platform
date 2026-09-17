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
  const inputQueues = new Map<
    string,
    { sequence: number; bytes: Uint8Array; base64: string }[]
  >();
  const inFlightInput = new Map<string, boolean>();

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
      inputQueues.delete(terminalId);
      inFlightInput.delete(terminalId);

      if (activeTerminalId.value === terminalId) {
        activeTerminalId.value = sessions.value[0]?.terminal_id || '';
      }
    }
  }

  // 输入单飞串行队列发送
  async function sendInput(terminalId: string, textOrBytes: string | Uint8Array) {
    if (!projectId.value || !threadId.value || disposed) return;

    let rawBytes: Uint8Array;
    if (typeof textOrBytes === 'string') {
      rawBytes = new TextEncoder().encode(textOrBytes);
    } else {
      rawBytes = textOrBytes;
    }

    if (rawBytes.length === 0) return;

    // 找到会话以获取 next_input_sequence
    const session = sessions.value.find((s) => s.terminal_id === terminalId);
    if (!session || session.status === 'exited') return;

    let queue = inputQueues.get(terminalId);
    if (!queue) {
      queue = [];
      inputQueues.set(terminalId, queue);
    }

    // 转 Base64
    let binaryStr = '';
    for (let i = 0; i < rawBytes.length; i++) {
      binaryStr += String.fromCharCode(rawBytes[i]);
    }
    const b64 = btoa(binaryStr);

    queue.push({
      sequence: session.next_input_sequence,
      bytes: rawBytes,
      base64: b64,
    });

    void processInputQueue(terminalId);
  }

  async function processInputQueue(terminalId: string) {
    if (inFlightInput.get(terminalId)) return;
    const queue = inputQueues.get(terminalId);
    if (!queue || queue.length === 0) return;

    const item = queue[0];
    inFlightInput.set(terminalId, true);

    try {
      const ack = await sendTerminalInput(
        projectId.value,
        threadId.value,
        terminalId,
        {
          sequence: item.sequence,
          data_base64: item.base64,
        },
      );

      // 更新会话的 sequence
      const session = sessions.value.find((s) => s.terminal_id === terminalId);
      if (session) {
        session.next_input_sequence = ack.next_input_sequence;
      }

      // 如果全部确认
      if (ack.accepted_bytes >= item.bytes.byteLength) {
        queue.shift();
      } else {
        // 部分确认，保留剩余字节
        const remaining = item.bytes.subarray(ack.accepted_bytes);
        let binaryStr = '';
        for (let i = 0; i < remaining.length; i++) {
          binaryStr += String.fromCharCode(remaining[i]);
        }
        item.bytes = remaining;
        item.base64 = btoa(binaryStr);
        item.sequence = ack.next_input_sequence;
      }
    } catch (err: unknown) {
      console.warn('终端输入发送异常:', err);
    } finally {
      inFlightInput.set(terminalId, false);
      if (queue.length > 0) {
        void processInputQueue(terminalId);
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
        inputQueues.clear();
        inFlightInput.clear();

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
