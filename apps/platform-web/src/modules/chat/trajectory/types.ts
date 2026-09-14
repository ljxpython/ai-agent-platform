/**
 * 轨迹排障视图核心数据模型定义
 */

export type TrajectoryRecordKind =
  | "system"
  | "context"
  | "user"
  | "assistant"
  | "tool"
  | "reasoning"
  | "subagent";

export type TrajectoryRecordStatus = "running" | "completed" | "error";

export interface TrajectoryTokens {
  input?: number;
  output?: number;
  reasoning?: number;
}

export interface TrajectoryRecord {
  /** 唯一稳定标识 */
  id: string;
  /** 会话轮次 (1-based) */
  turnIndex: number;
  /** 轮次内的步骤编号 (1-based) */
  stepIndex: number;
  /** 事件类型 */
  kind: TrajectoryRecordKind;
  /** 标题或动作名称，例如 "用户提问", "web_search", "AI 思考" */
  name: string;
  /** 单行精简摘要 */
  summary: string;
  /** 状态 */
  status: TrajectoryRecordStatus;
  /** 开始时间戳或时间字符串 */
  startedAt?: string | number | null;
  /** 执行耗时 (毫秒) */
  durationMs?: number | null;
  /** Token 消耗统计 */
  tokens?: TrajectoryTokens;
  /** 输入载荷或提问文本 */
  input?: unknown;
  /** 输出结果或最终文本 */
  output?: unknown;
  /** 思考过程文本 (若有) */
  reasoning?: string;
  /** 错误信息 (若有) */
  error?: string;
  /** 原始底层数据对象 */
  raw?: unknown;
}

export interface TrajectoryTurnGroup {
  turnIndex: number;
  records: TrajectoryRecord[];
}
