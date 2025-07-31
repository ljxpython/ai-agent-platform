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
  public async sendQuery(query: string, connectionId?: number): Promise<boolean> {
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
        ...(connectionId !== undefined && { connection_id: connectionId.toString() })
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
    };

    this.eventSource.onmessage = (event) => {
      this.handleMessage(event);
    };

    this.eventSource.onerror = (error) => {
      console.error('SSE连接错误:', error);
      this.handleDisconnect();
    };

    // 监听特定事件类型
    this.eventSource.addEventListener('message', (event) => {
      this.handleMessage(event);
    });

    this.eventSource.addEventListener('result', (event) => {
      this.handleFinalResult(event);
    });

    this.eventSource.addEventListener('error', (event) => {
      console.error('SSE连接错误:', event);
      this.handleDisconnect();
    });

    this.eventSource.addEventListener('end', (event) => {
      console.log('SSE流结束');
      this.disconnect();
    });
  }

  /**
   * 处理SSE消息
   */
  private handleMessage(event: MessageEvent): void {
    try {
      console.log('收到SSE消息:', event.data);
      const data = JSON.parse(event.data);

      // 处理不同类型的消息
      if (data.type === 'message') {
        const message: StreamResponseMessage = {
          source: data.source || '系统',
          content: data.content || '',
          is_final: data.is_final || false,
          region: data.region || null,
          type: data.message_type || 'text'
        };

        // 特殊处理：设置默认区域
        if (message.source === '查询分析智能体' && !message.region) {
          message.region = 'analysis';
        }
        if (message.source === '可视化推荐智能体' && !message.region) {
          message.region = 'visualization';
        }

        console.log('处理消息:', message);
        if (this.onMessageCallback) {
          this.onMessageCallback(message);
        }

        // 处理最终结果
        if (data.is_final && data.result) {
          this.handleFinalResultData(data);
        }
      }
    } catch (error) {
      console.error('处理SSE消息时出错:', error);
      if (this.onErrorCallback) {
        this.onErrorCallback(new Error('处理SSE消息时出错'));
      }
    }
  }

  /**
   * 处理最终结果事件
   */
  private handleFinalResult(event: MessageEvent): void {
    try {
      console.log('收到最终结果:', event.data);
      const data = JSON.parse(event.data);

      if (this.onResultCallback && data.result) {
        this.onResultCallback(data.result);
      }

      // 处理完成后关闭连接
      this.disconnect();
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
    if (data.result) {
      console.log('处理最终结果数据:', data.result);

      // SQL结果
      if (data.result.sql && this.onFinalSqlCallback) {
        this.onFinalSqlCallback(data.result.sql);
      }

      // 解释结果
      if (data.result.explanation && this.onFinalExplanationCallback) {
        this.onFinalExplanationCallback(data.result.explanation);
      }

      // 数据结果
      if (data.result.results && this.onFinalDataCallback) {
        this.onFinalDataCallback(data.result.results);
      }

      // 可视化结果
      if (this.onFinalVisualizationCallback &&
          (data.result.visualization_type || data.result.visualization_config)) {
        this.onFinalVisualizationCallback({
          type: data.result.visualization_type || '',
          config: data.result.visualization_config || {}
        });
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
  connectionId?: number
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
    sse.sendQuery(query, connectionId);
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
export let globalWebSocketState = globalSSEState;
export let globalWebSocketError = globalSSEError;
