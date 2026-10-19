/**
 * 有界内存错误缓冲区 (Error Ring Buffer)
 * 用于在前端内存中暂存最近的 HTTP 失败、SSE 异常和 JS 运行时报错，容量默认 10 条，先进先出 (FIFO)。
 * 严格保护内存，杜绝内存泄漏。
 */

export type DiagnosticErrorType = "http" | "sse" | "js_runtime" | "route";

export interface DiagnosticErrorRecord {
  id: string;
  timestamp: string;
  type: DiagnosticErrorType;
  status?: number;
  requestId?: string;
  url?: string;
  method?: string;
  code?: string;
  message: string;
  detail?: unknown;
  stack?: string;
}

export class ErrorRingBuffer {
  private buffer: DiagnosticErrorRecord[] = [];
  private readonly capacity: number;
  private counter = 0;

  constructor(capacity = 10) {
    this.capacity = Math.max(1, capacity);
  }

  /**
   * 推入一条错误记录，超过容量上限时自动丢弃最旧记录
   */
  push(
    record: Omit<DiagnosticErrorRecord, "id" | "timestamp"> & {
      timestamp?: string;
    },
  ): DiagnosticErrorRecord {
    this.counter += 1;
    const item: DiagnosticErrorRecord = {
      id: `err-${Date.now()}-${this.counter}`,
      timestamp: record.timestamp || new Date().toISOString(),
      ...record,
    };

    if (this.buffer.length >= this.capacity) {
      this.buffer.shift();
    }
    this.buffer.push(item);
    return item;
  }

  /**
   * 获取所有记录，默认按时间倒序排列 (最新的在最前)
   */
  getAll(): DiagnosticErrorRecord[] {
    return [...this.buffer].reverse();
  }

  /**
   * 获取最新一条错误记录
   */
  getLatest(): DiagnosticErrorRecord | null {
    if (this.buffer.length === 0) return null;
    return this.buffer[this.buffer.length - 1];
  }

  /**
   * 按 Request ID 查询最新匹配的错误
   */
  getLatestByRequestId(requestId: string): DiagnosticErrorRecord | null {
    if (!requestId) return null;
    for (let i = this.buffer.length - 1; i >= 0; i--) {
      if (this.buffer[i].requestId === requestId) {
        return this.buffer[i];
      }
    }
    return null;
  }

  /**
   * 获取当前缓存数量
   */
  get size(): number {
    return this.buffer.length;
  }

  /**
   * 清空缓冲区 (通常用于测试或明确重置)
   */
  clear(): void {
    this.buffer = [];
  }
}

export const errorRingBuffer = new ErrorRingBuffer(10);
