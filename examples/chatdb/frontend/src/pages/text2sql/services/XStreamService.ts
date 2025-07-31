// 基于Ant Design X的流式服务
import { XStream } from '@ant-design/x';

// 流式消息类型 - 与后端SSE格式对应
export interface XStreamMessage {
  id: string;
  type: 'message' | 'result' | 'error' | 'complete' | 'session' | 'close';
  region: 'analysis' | 'sql' | 'explanation' | 'data' | 'visualization' | 'process';
  content: string;
  source: string;
  timestamp: string;
  is_final: boolean;
  session_id?: string;
  status?: string;
  metadata?: Record<string, any>;
}

// 流式响应处理器
export interface XStreamHandler {
  onMessage: (message: XStreamMessage) => void;
  onError: (error: Error) => void;
  onComplete: () => void;
  onSessionInit?: (sessionId: string) => void;
}

// 区域消息聚合器 - 用于管理不同区域的消息
export interface RegionMessageAggregator {
  [region: string]: {
    messages: XStreamMessage[];
    content: string;
    isStreaming: boolean;
    hasContent: boolean;
    lastUpdate: string;
  };
}

// 简化的SSE数据解析函数
const parseSSEData = (data: string): XStreamMessage | null => {
  try {
    const parsed = JSON.parse(data);

    console.log('SSE解析数据:', parsed);

    // 直接使用后端返回的数据结构
    const message: XStreamMessage = {
      id: parsed.message_id || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type: parsed.type || 'message',
      region: parsed.region || 'process',
      content: parsed.content || '',
      source: parsed.source || '系统',
      timestamp: parsed.timestamp || new Date().toISOString(),
      is_final: parsed.is_final || false,
      session_id: parsed.session_id,
      status: parsed.status,
      metadata: parsed.metadata
    };

    return message;
  } catch (error) {
    console.error('解析SSE数据失败:', error, 'data:', data);
    return null;
  }
};

// 简化的SSE服务类
export class XStreamService {
  private baseUrl: string;
  private isActive = false;
  private currentSessionId: string | null = null;
  private eventSource: EventSource | null = null;

  constructor(baseUrl: string = 'http://localhost:8000/api/text2sql-sse/stream') {
    this.baseUrl = baseUrl;
  }

  // 启动流式请求
  async startStream(
    query: string,
    handler: XStreamHandler,
    options: {
      connectionId?: number;
      sessionId?: string;
    } = {}
  ): Promise<void> {
    try {
      // 停止当前流
      await this.stopStream();

      // 生成会话ID
      this.currentSessionId = options.sessionId || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // 构建请求参数
      const params = new URLSearchParams({
        query,
        session_id: this.currentSessionId,
        ...(options.connectionId && { connection_id: options.connectionId.toString() })
      });

      const sseUrl = `${this.baseUrl}?${params.toString()}`;
      console.log('启动SSE连接:', sseUrl);

      // 创建EventSource连接
      this.eventSource = new EventSource(sseUrl);
      this.isActive = true;

      // 设置事件监听器
      this.setupEventListeners(handler);

    } catch (error) {
      console.error('启动流式请求失败:', error);
      handler.onError(error instanceof Error ? error : new Error(String(error)));
    }
  }

  // 设置EventSource事件监听器
  private setupEventListeners(handler: XStreamHandler): void {
    if (!this.eventSource) return;

    // 监听所有事件类型
    const eventTypes = ['message', 'result', 'error', 'complete', 'session', 'close', 'final_result'];

    eventTypes.forEach(eventType => {
      this.eventSource!.addEventListener(eventType, (event) => {
        if (!this.isActive) return;

        console.log(`收到SSE事件 [${eventType}]:`, event.data);

        const message = parseSSEData(event.data);
        if (message) {
          // 处理会话初始化消息
          if (message.type === 'session' && message.session_id && handler.onSessionInit) {
            handler.onSessionInit(message.session_id);
          }

          // 处理消息
          handler.onMessage(message);

          // 检查是否是最终消息
          if (message.is_final || message.type === 'complete' || message.type === 'close') {
            console.log('收到最终消息，停止流');
            this.stopStream();
            handler.onComplete();
          }
        }
      });
    });

    // 监听连接打开
    this.eventSource.onopen = () => {
      console.log('SSE连接已建立');
    };

    // 监听连接错误
    this.eventSource.onerror = (error) => {
      console.error('SSE连接错误:', error);
      this.isActive = false;
      handler.onError(new Error('SSE连接错误'));
    };
  }

  // 停止流
  async stopStream(): Promise<void> {
    this.isActive = false;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.currentSessionId = null;
  }

  // 检查是否活跃
  isStreamActive(): boolean {
    return this.isActive;
  }

  // 获取当前会话ID
  getCurrentSessionId(): string | null {
    return this.currentSessionId;
  }

  // 发送用户反馈
  async sendFeedback(
    sessionId: string,
    feedback: string,
    type: 'approve' | 'feedback' | 'cancel' = 'feedback'
  ): Promise<void> {
    try {
      const feedbackUrl = `http://localhost:8000/api/text2sql-sse/feedback/${sessionId}`;
      const response = await fetch(feedbackUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: feedback,
          type
        }),
      });

      if (!response.ok) {
        throw new Error(`发送反馈失败: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error('发送反馈失败:', error);
      throw error;
    }
  }
}

// 创建全局实例
export const xStreamService = new XStreamService();

// 便捷函数
export const createStreamHandler = (
  onMessage: (message: XStreamMessage) => void,
  onError: (error: Error) => void,
  onComplete: () => void = () => {}
): XStreamHandler => ({
  onMessage,
  onError,
  onComplete
});

// 消息类型检查工具
export const isMessageType = (message: XStreamMessage, type: XStreamMessage['type']): boolean => {
  return message.type === type;
};

export const isRegionMessage = (message: XStreamMessage, region: XStreamMessage['region']): boolean => {
  return message.region === region;
};

export const isFinalMessage = (message: XStreamMessage): boolean => {
  return message.is_final === true;
};

// 区域消息聚合器类 - 用于管理不同区域的消息
export class RegionMessageManager {
  private regions: RegionMessageAggregator = {};

  // 添加消息到指定区域
  addMessage(message: XStreamMessage): void {
    const region = message.region;

    if (!this.regions[region]) {
      this.regions[region] = {
        messages: [],
        content: '',
        isStreaming: false,
        hasContent: false,
        lastUpdate: message.timestamp
      };
    }

    this.regions[region].messages.push(message);

    // 根据消息类型更新内容
    if (message.type === 'message') {
      // 流式消息，累积追加内容
      this.regions[region].content += message.content;
      this.regions[region].isStreaming = !message.is_final;
    } else if (message.type === 'result') {
      // 最终结果，替换内容
      this.regions[region].content = message.content;
      this.regions[region].isStreaming = false;
    } else if (message.type === 'error') {
      // 错误消息，替换内容
      this.regions[region].content = message.content;
      this.regions[region].isStreaming = false;
    } else if (message.type === 'session') {
      // 会话消息，不更新内容
      return;
    }

    this.regions[region].hasContent = this.regions[region].content.length > 0;
    this.regions[region].lastUpdate = message.timestamp;

    // 调试日志
    console.log(`RegionMessageManager: 添加消息到区域 ${region}`, {
      type: message.type,
      contentLength: message.content.length,
      totalContentLength: this.regions[region].content.length,
      isStreaming: this.regions[region].isStreaming,
      hasContent: this.regions[region].hasContent,
      isFinal: message.is_final,
      source: message.source,
      content: message.content.substring(0, 50) + (message.content.length > 50 ? '...' : '')
    });
  }

  // 获取指定区域的信息
  getRegion(region: string) {
    return this.regions[region] || {
      messages: [],
      content: '',
      isStreaming: false,
      hasContent: false,
      lastUpdate: new Date().toISOString()
    };
  }

  // 获取所有区域
  getAllRegions(): RegionMessageAggregator {
    return { ...this.regions };
  }

  // 重置所有区域
  reset(): void {
    this.regions = {};
  }

  // 停止所有区域的流式状态
  stopAllStreaming(): void {
    Object.keys(this.regions).forEach(region => {
      this.regions[region].isStreaming = false;
    });
  }
}
