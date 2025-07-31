import { Text2SQLResponse } from './types';
import axios from 'axios';

// 创建API实例
const api = axios.create({
  baseURL: 'http://localhost:8000/api',
});

// 获取数据库连接列表
export const getConnections = () => api.get('/connections');

// 流式响应消息
export interface StreamResponseMessage {
  source: string;
  content: string;
  is_final?: boolean;
  region?: string;
  type?: string;
  is_feedback_response?: boolean;
}

export interface FinalSqlData {
  sql: string;
}

export interface FinalExplanationData {
  explanation: string;
}

export interface FinalDataResult {
  results: any[];
}

export interface FinalVisualizationData {
  type: string;
  config: any;
}

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// SSE连接状态枚举
export enum SSEConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
  RECONNECTING = 'reconnecting'
}

// 全局SSE状态，用于UI显示
export let globalSSEState: SSEConnectionState = SSEConnectionState.DISCONNECTED;

// 全局SSE错误信息
export let globalSSEError: string | null = null;

// 上次错误时间戳，用于防止频繁显示错误
let lastErrorTimestamp: number = 0;

// 更新全局状态的函数（声明）
let updateGlobalStates: () => void;

/**
 * Text2SQL SSE连接类，管理Text2SQL的SSE通信
 */
export class Text2SQLSSE {
  private eventSource: EventSource | null = null;
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectTimeout: number = 2000; // 开始重连时间(ms)
  private reconnectTimeoutId: NodeJS.Timeout | null = null;
  private baseUrl: string;
  private connectionState: SSEConnectionState = SSEConnectionState.DISCONNECTED;
  private backendAvailable: boolean = true; // 标记后端是否可用
  private currentSessionId: string | null = null;

  // 回调函数
  private onMessageCallback: ((message: StreamResponseMessage) => void) | null = null;
  private onResultCallback: ((result: Text2SQLResponse) => void) | null = null;
  private onErrorCallback: ((error: Error) => void) | null = null;
  private onFinalSqlCallback: ((data: string) => void) | null = null;
  private onFinalExplanationCallback: ((data: string) => void) | null = null;
  private onFinalDataCallback: ((data: any[]) => void) | null = null;
  private onFinalVisualizationCallback: ((data: FinalVisualizationData) => void) | null = null;

  constructor() {
    // 使用SSE端点
    this.baseUrl = `${API_BASE_URL}/text2sql-sse/stream`;

    // 输出调试信息
    console.log('SSE Base URL:', this.baseUrl);
    console.log('API_BASE_URL:', API_BASE_URL);

    // 启用SSE功能
    this.backendAvailable = true;
    console.log('✅ SSE功能已启用，后端端点可用');
  }

  /**
   * 建立SSE连接（用于测试连接）
   */
  public async connect(): Promise<boolean> {
    if (this.isConnected) {
      console.log('SSE已连接');
      return true;
    }

    // 如果后端被标记为不可用，不尝试连接
    if (!this.backendAvailable) {
      console.log('后端服务可能不可用，不尝试连接');
      this.notifyError(new Error('后端服务不可用，请稍后再试'));
      return false;
    }

    console.log('正在测试SSE连接...');
    this.connectionState = SSEConnectionState.CONNECTING;
    globalSSEState = SSEConnectionState.CONNECTING;

    try {
      // 测试连接可用性
      const response = await fetch(`${API_BASE_URL}/text2sql-sse/health`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
      });

      if (response.ok) {
        console.log('SSE端点可用');
        this.isConnected = true;
        this.connectionState = SSEConnectionState.CONNECTED;
        globalSSEState = SSEConnectionState.CONNECTED;
        this.reconnectAttempts = 0;
        this.backendAvailable = true;
        globalSSEError = null;
        return true;
      } else {
        throw new Error(`SSE端点不可用: ${response.status}`);
      }
    } catch (error) {
      console.error('SSE连接测试失败:', error);
      this.connectionState = SSEConnectionState.ERROR;
      globalSSEState = SSEConnectionState.ERROR;
      globalSSEError = 'SSE连接测试失败';
      this.notifyError(new Error('SSE连接测试失败'));
      return false;
    }
  }

  /**
   * 发送查询到SSE
   */
  public async sendQuery(query: string, connectionId?: number, userFeedbackEnabled?: boolean): Promise<boolean> {
    if (!this.backendAvailable) {
      this.notifyError(new Error('后端服务不可用'));
      return false;
    }

    try {
      console.log('发送查询到SSE:', query);

      // 生成会话ID
      this.currentSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // 构建查询URL
      const queryParams = new URLSearchParams({
        query: query,
        session_id: this.currentSessionId,
        ...(connectionId !== undefined && { connection_id: connectionId.toString() }),
        ...(userFeedbackEnabled !== undefined && { user_feedback_enabled: userFeedbackEnabled.toString() })
      });

      const sseUrl = `${this.baseUrl}?${queryParams.toString()}`;
      console.log('SSE URL:', sseUrl);

      // 关闭现有连接
      if (this.eventSource) {
        this.eventSource.close();
      }

      // 创建新的SSE连接
      this.eventSource = new EventSource(sseUrl);

      // 设置事件监听器
      this.setupEventListeners();

      return true;
    } catch (error) {
      console.error('发送查询错误:', error);
      this.notifyError(new Error(`发送查询失败: ${error}`));
      return false;
    }
  }

  /**
   * 设置SSE事件监听器
   */
  private setupEventListeners(): void {
    if (!this.eventSource) return;

    this.eventSource.onopen = () => {
      console.log('SSE连接已建立');
      this.isConnected = true;
      this.connectionState = SSEConnectionState.CONNECTED;
      globalSSEState = SSEConnectionState.CONNECTED;
      globalSSEError = null;
      updateGlobalStates();
    };

    // 使用统一的消息处理器
    this.eventSource.onmessage = (event) => {
      this.handleMessage(event);
    };

    this.eventSource.onerror = (error) => {
      console.error('SSE连接错误:', error);
      this.handleDisconnect();
    };

    // 监听特定事件类型（不重复监听message）
    this.eventSource.addEventListener('result', (event) => {
      this.handleFinalResult(event);
    });

    this.eventSource.addEventListener('final_result', (event) => {
      this.handleFinalResult(event);
    });

    this.eventSource.addEventListener('close', (event) => {
      console.log('SSE流结束');
      this.disconnect();
    });

    this.eventSource.addEventListener('end', (event) => {
      console.log('SSE流结束');
      this.disconnect();
    });
  }

  /**
   * 处理SSE消息 - 优化版本
   */
  private handleMessage(event: MessageEvent): void {
    try {
      // 减少日志输出，避免控制台刷屏
      console.log('🔔 收到SSE消息');

      // 检查是否是完整的SSE格式（包含event:, id:, data:）
      let jsonData = event.data;
      if (typeof event.data === 'string' && event.data.includes('data:')) {
        // 提取data:后面的JSON部分
        const lines = event.data.split('\n');
        for (const line of lines) {
          if (line.startsWith('data:')) {
            jsonData = line.substring(5).trim(); // 移除"data:"前缀
            break;
          }
        }
      }

      // 尝试解析JSON
      let data: any;
      try {
        data = JSON.parse(jsonData);
      } catch (parseError) {
        // 如果不是JSON，作为纯文本处理
        const message: StreamResponseMessage = {
          source: '系统',
          content: jsonData,
          is_final: false,
          region: 'process',
          type: 'text'
        };

        if (this.onMessageCallback) {
          this.onMessageCallback(message);
        }
        return;
      }

      // 过滤完全空的消息（但保留包含空格和换行的内容）
      if (!data.content && !data.message) {
        return;
      }

      // 处理各种类型的消息
      const inferredRegion = this.inferRegionFromSource(data.source);
      const message: StreamResponseMessage = {
        source: data.source || '系统',
        content: data.content || data.message || '',
        is_final: data.is_final || false,
        region: data.region || inferredRegion,
        type: data.type || data.message_type || 'text'
      };

      // 对于分析区域，保留所有空格和换行符，因为这些对markdown格式很重要
      // 对于其他区域，过滤完全空的内容
      const shouldSendMessage = message.region === 'analysis'
        ? message.content.length > 0  // 分析区域：只要有内容就发送
        : message.content.trim().length > 0;  // 其他区域：过滤空白内容

      if (shouldSendMessage) {
        // 添加调试信息，特别关注分析区域的内容格式
        if (message.region === 'analysis') {
          console.log(`📤 [分析区域] 发送消息:`, {
            region: message.region,
            contentLength: message.content.length,
            contentPreview: message.content.substring(0, 50),
            hasNewlines: message.content.includes('\n'),
            hasSpaces: message.content.includes(' '),
            rawContent: JSON.stringify(message.content.substring(0, 50))
          });
        } else {
          console.log(`📤 发送消息: ${message.region} - ${message.content.substring(0, 50)}...`);
        }

        if (this.onMessageCallback) {
          this.onMessageCallback(message);
        }
      }

      // 处理最终结果
      if (data.is_final && data.result) {
        this.handleFinalResultData(data);
      }

    } catch (error) {
      console.error('处理SSE消息时出错:', error);

      // 尝试作为纯文本处理
      try {
        const fallbackMessage: StreamResponseMessage = {
          source: '系统',
          content: `收到消息: ${event.data}`,
          is_final: false,
          region: 'process',
          type: 'text'
        };

        if (this.onMessageCallback) {
          this.onMessageCallback(fallbackMessage);
        }
      } catch (fallbackError) {
        console.error('备用消息处理也失败:', fallbackError);
        if (this.onErrorCallback) {
          this.onErrorCallback(new Error('处理SSE消息时出错，请检查网络连接或稍后再试。'));
        }
      }
    }
  }

  /**
   * 根据消息来源推断区域
   */
  private inferRegionFromSource(source?: string): string {
    if (!source) return 'process';

    const sourceLower = source.toLowerCase();
    if (sourceLower.includes('分析') || sourceLower.includes('analyzer')) {
      return 'analysis';
    }
    if (sourceLower.includes('sql') || sourceLower.includes('生成')) {
      return 'sql';
    }
    if (sourceLower.includes('解释') || sourceLower.includes('explainer')) {
      return 'explanation';
    }
    if (sourceLower.includes('执行') || sourceLower.includes('executor')) {
      return 'data';
    }
    if (sourceLower.includes('可视化') || sourceLower.includes('visualization')) {
      return 'visualization';
    }

    return 'process';
  }

  /**
   * 处理最终结果事件
   */
  private handleFinalResult(event: MessageEvent): void {
    try {
      console.log('收到最终结果:', event.data);

      let data: any;
      try {
        data = JSON.parse(event.data);
      } catch (parseError) {
        console.error('解析最终结果JSON失败:', parseError);
        return;
      }

      // 处理最终结果数据
      if (data.result) {
        this.handleFinalResultData(data);

        if (this.onResultCallback) {
          this.onResultCallback(data.result);
        }
      }

      // 发送完成消息
      if (this.onMessageCallback) {
        this.onMessageCallback({
          source: '系统',
          content: '查询处理完成',
          is_final: true,
          region: 'process',
          type: 'completion'
        });
      }

      // 处理完成后关闭连接
      setTimeout(() => {
        this.disconnect();
      }, 1000); // 延迟1秒关闭，确保消息都被处理

    } catch (error) {
      console.error('处理最终结果失败:', error);
      if (this.onErrorCallback) {
        this.onErrorCallback(new Error('处理最终结果失败'));
      }
    }
  }

  /**
   * 处理错误事件
   */
  private handleError(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data);
      console.error('收到错误事件:', data);

      if (this.onErrorCallback) {
        this.onErrorCallback(new Error(data.message || '服务器错误'));
      }
    } catch (error) {
      console.error('处理错误事件失败:', error);
      if (this.onErrorCallback) {
        this.onErrorCallback(new Error('处理错误事件失败'));
      }
    }
  }

  /**
   * 处理最终结果数据
   */
  private handleFinalResultData(data: any): void {
    try {
      if (data.result) {
        console.log('处理最终结果数据:', data.result);

        // SQL结果
        if (data.result.sql && this.onFinalSqlCallback) {
          console.log('处理SQL结果:', data.result.sql);
          this.onFinalSqlCallback(data.result.sql);
        }

        // 解释结果 - 不再通过最终结果回调处理，避免重复显示
        // 解释内容已通过流式消息处理，这里只记录日志
        if (data.result.explanation) {
          console.log('收到解释结果(已通过流式处理):', data.result.explanation.substring(0, 100) + '...');
          // 注释掉回调，避免重复显示
          // this.onFinalExplanationCallback(data.result.explanation);
        }

        // 数据结果
        if (data.result.results && this.onFinalDataCallback) {
          console.log('处理数据结果:', data.result.results);
          this.onFinalDataCallback(data.result.results);
        }

        // 可视化结果
        if (this.onFinalVisualizationCallback &&
            (data.result.visualization_type || data.result.visualization_config)) {
          console.log('处理可视化结果:', {
            type: data.result.visualization_type,
            config: data.result.visualization_config
          });
          this.onFinalVisualizationCallback({
            type: data.result.visualization_type || '',
            config: data.result.visualization_config || {}
          });
        }

        // 发送最终结果消息到界面
        if (this.onMessageCallback) {
          let resultSummary = '查询结果已生成：';
          if (data.result.sql) resultSummary += ' SQL语句';
          if (data.result.explanation) resultSummary += ' 解释说明';
          if (data.result.results) resultSummary += ` 数据(${data.result.results.length}行)`;
          if (data.result.visualization_type) resultSummary += ' 可视化图表';

          this.onMessageCallback({
            source: '系统',
            content: resultSummary,
            is_final: true,
            region: 'process',
            type: 'completion'
          });
        }
      }
    } catch (error) {
      console.error('处理最终结果数据时出错:', error);
      if (this.onErrorCallback) {
        this.onErrorCallback(new Error('处理最终结果数据时出错'));
      }
    }
  }

  /**
   * 设置回调函数
   */
  public setCallbacks(
    onMessage: (message: StreamResponseMessage) => void,
    onResult: (result: Text2SQLResponse) => void,
    onError: (error: Error) => void,
    onFinalSql?: (data: string) => void,
    onFinalExplanation?: (data: string) => void,
    onFinalData?: (data: any[]) => void,
    onFinalVisualization?: (data: FinalVisualizationData) => void
  ): void {
    this.onMessageCallback = onMessage;
    this.onResultCallback = onResult;
    this.onErrorCallback = onError;
    this.onFinalSqlCallback = onFinalSql || null;
    this.onFinalExplanationCallback = onFinalExplanation || null;
    this.onFinalDataCallback = onFinalData || null;
    this.onFinalVisualizationCallback = onFinalVisualization || null;
  }

  /**
   * 断开SSE连接
   */
  public disconnect(): void {
    console.log('断开SSE连接');

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.isConnected = false;
    this.connectionState = SSEConnectionState.DISCONNECTED;
    globalSSEState = SSEConnectionState.DISCONNECTED;
    this.currentSessionId = null;

    // 清除重连定时器
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
  }

  /**
   * 处理连接断开
   */
  private handleDisconnect(): void {
    console.log('SSE连接断开');
    this.isConnected = false;
    this.connectionState = SSEConnectionState.DISCONNECTED;
    globalSSEState = SSEConnectionState.DISCONNECTED;

    // 判断是否需要重连
    if (this.reconnectAttempts >= 2) {
      this.backendAvailable = false;
      console.log('多次重连失败，标记后端服务可能不可用');
    }

    // 只有在后端可能可用时才尝试重连
    if (this.backendAvailable) {
      this.attemptReconnect();
    }
  }

  /**
   * 尝试重新连接
   */
  private attemptReconnect(): void {
    if (!this.backendAvailable) {
      console.log('后端服务可能不可用，不尝试重连');
      this.notifyError(new Error('后端服务不可用，请稍后再试'));
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('达到最大重连次数，停止重连');
      this.notifyError(new Error('无法连接到服务器，请稍后再试'));
      this.backendAvailable = false;
      return;
    }

    globalSSEState = SSEConnectionState.RECONNECTING;

    const delay = this.reconnectTimeout * Math.pow(1.5, this.reconnectAttempts);
    console.log(`${delay}ms后尝试重连(第${this.reconnectAttempts + 1}次)`);

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  /**
   * 通知错误
   */
  private notifyError(error: Error): void {
    const now = Date.now();
    if (now - lastErrorTimestamp > 5000) { // 5秒内不重复显示相同错误
      globalSSEError = error.message;
      lastErrorTimestamp = now;

      if (this.onErrorCallback) {
        this.onErrorCallback(error);
      }
    }
  }

  /**
   * 获取连接状态
   */
  public getConnectionState(): SSEConnectionState {
    return this.connectionState;
  }

  /**
   * 检查是否已连接
   */
  public isSSEConnected(): boolean {
    return this.isConnected;
  }

  /**
   * 发送消息（SSE不支持，保持兼容性）
   */
  public sendMessage(message: string): void {
    console.warn('SSE不支持发送消息，忽略消息:', message);
    // SSE是单向通信，不支持发送消息
    // 这个方法只是为了保持与WebSocket API的兼容性
  }

  /**
   * 获取当前会话ID
   */
  public getCurrentSessionId(): string | null {
    return this.currentSessionId;
  }
}

// 创建全局SSE实例
let sseInstance: Text2SQLSSE | null = null;

/**
 * 获取SSE实例
 */
export const getSSEInstance = (): Text2SQLSSE => {
  if (!sseInstance) {
    sseInstance = new Text2SQLSSE();
  }
  return sseInstance;
};

/**
 * 使用SSE发送Text2SQL请求
 */
export const sendSSEText2SQLRequest = (
  query: string,
  onMessage: (message: StreamResponseMessage) => void,
  onResult: (result: Text2SQLResponse) => void,
  onError: (error: Error) => void,
  onFinalSql?: (data: string) => void,
  onFinalExplanation?: (data: string) => void,
  onFinalData?: (data: any[]) => void,
  onFinalVisualization?: (data: FinalVisualizationData) => void,
  connectionId?: number,
  userFeedbackEnabled?: boolean
): void => {
  try {
    const sse = getSSEInstance();
    sse.setCallbacks(
      onMessage,
      onResult,
      onError,
      onFinalSql,
      onFinalExplanation,
      onFinalData,
      onFinalVisualization
    );
    sse.sendQuery(query, connectionId, userFeedbackEnabled);
  } catch (error) {
    console.error('SSE请求错误:', error);
    onError(error instanceof Error ? error : new Error(String(error)));
  }
};

/**
 * 关闭SSE连接
 */
export const closeSSEConnection = (): void => {
  if (sseInstance) {
    sseInstance.disconnect();
  }
};

/**
 * 发送标准Text2SQL请求（非流式）
 */
export const sendText2SQLRequest = async (query: string): Promise<Text2SQLResponse> => {
  try {
    const response = await fetch(`${API_BASE_URL}/text2sql/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || '请求处理失败');
    }

    return await response.json();
  } catch (error) {
    console.error('API请求失败:', error);
    throw error;
  }
};

// 兼容性导出，保持与原WebSocket API相同的接口
export const sendWebSocketText2SQLRequest = sendSSEText2SQLRequest;
export const closeWebSocketConnection = closeSSEConnection;
export const getWebSocketInstance = getSSEInstance;

// 导出状态相关的变量和枚举，保持兼容性
export const WebSocketConnectionState = SSEConnectionState;

// 创建响应式的全局状态变量
export const getGlobalWebSocketState = () => globalSSEState;
export const getGlobalWebSocketError = () => globalSSEError;

// 为了兼容性，导出变量引用
export let globalWebSocketState: SSEConnectionState = globalSSEState;
export let globalWebSocketError: string | null = globalSSEError;

// 更新全局状态的函数实现
updateGlobalStates = () => {
  globalWebSocketState = globalSSEState;
  globalWebSocketError = globalSSEError;
};

// 导出更新函数
export { updateGlobalStates };

// 导出SSE反馈功能
export { sendUserFeedback, sendUserApproval } from './sse-api';
