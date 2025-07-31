// API基础URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// WebSocket连接状态枚举
export enum WebSocketConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
  RECONNECTING = 'reconnecting'
}

// 全局WebSocket状态
export let globalWebSocketState: WebSocketConnectionState = WebSocketConnectionState.DISCONNECTED;

// 全局WebSocket错误信息
export let globalWebSocketError: string | null = null;

// 上次错误时间戳，用于防止频繁显示错误
let lastErrorTimestamp: number = 0;

// 错误防抖时间（毫秒）
const ERROR_DEBOUNCE_MS = 5000;

// 事件监听器类型
type EventListener = (...args: any[]) => void;

/**
 * WebSocket连接管理器
 *
 * 管理与后端WebSocket服务的连接，支持多用户同时访问
 */
export class WebSocketManager {
  private eventListeners: Map<string, EventListener[]> = new Map();
  private socket: WebSocket | null = null;
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectTimeout: number = 2000; // 开始重连时间(ms)
  private reconnectTimeoutId: NodeJS.Timeout | null = null;
  private heartbeatInterval: number = 30000; // 心跳间隔(ms)
  private heartbeatTimeoutId: NodeJS.Timeout | null = null;
  private url: string;
  private connectionState: WebSocketConnectionState = WebSocketConnectionState.DISCONNECTED;
  private backendAvailable: boolean = true; // 标记后端是否可用
  private connectionId: string | null = null;
  private userId: string | null = null;
  private messageHandlers: Map<string, (message: any) => void> = new Map();

  /**
   * 构造函数
   *
   * @param userId 可选的用户ID
   */
  constructor(userId?: string) {
    // 设置用户ID
    this.userId = userId || null;

    // 构建WebSocket URL
    this.url = `ws://${window.location.hostname}:8000/api/ws-manager/connect`;
    if (this.userId) {
      this.url += `?user_id=${encodeURIComponent(this.userId)}`;
    }

    // 输出调试信息
    console.log('WebSocket URL:', this.url);
    console.log('API_BASE_URL:', API_BASE_URL);
    console.log('Window location:', window.location.href);

    // 设置心跳检测间隔（60秒）
    this.heartbeatInterval = 60000;
    this.heartbeatTimeoutId = null;

    // 临时禁用WebSocket功能，避免持续的连接尝试
    this.backendAvailable = false;
    console.warn('⚠️ WebSocket管理器已临时禁用，避免持续的连接尝试');

  }

  /**
   * 添加事件监听器
   */
  public on(event: string, listener: EventListener): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(listener);
  }

  /**
   * 移除事件监听器
   */
  public off(event: string, listener: EventListener): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  /**
   * 触发事件
   */
  private emit(event: string, ...args: any[]): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(...args);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
  }

  /**
   * 移除所有事件监听器
   */
  public removeAllListeners(event?: string): void {
    if (event) {
      this.eventListeners.delete(event);
    } else {
      this.eventListeners.clear();
    }
  }

  /**
   * 建立WebSocket连接
   *
   * @returns Promise对象，表示连接是否成功
   */
  public connect(): Promise<boolean> {
    // 如果后端被标记为不可用，直接返回失败
    if (!this.backendAvailable) {
      console.log('后端服务可能不可用，不尝试连接');
      return Promise.resolve(false);
    }

    // 更新全局状态
    globalWebSocketState = WebSocketConnectionState.CONNECTING;
    this.connectionState = WebSocketConnectionState.CONNECTING;

    return new Promise((resolve, reject) => {
      if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
        console.log('WebSocket已连接或正在连接中');
        if (this.socket.readyState === WebSocket.OPEN) {
          globalWebSocketState = WebSocketConnectionState.CONNECTED;
          this.connectionState = WebSocketConnectionState.CONNECTED;
          resolve(true);
        } else {
          // 如果正在连接，等待连接完成
          const checkConnection = () => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
              globalWebSocketState = WebSocketConnectionState.CONNECTED;
              this.connectionState = WebSocketConnectionState.CONNECTED;
              resolve(true);
            } else if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
              setTimeout(checkConnection, 100); // 每100ms检查一次
            } else {
              globalWebSocketState = WebSocketConnectionState.ERROR;
              this.connectionState = WebSocketConnectionState.ERROR;
              reject(new Error('WebSocket连接失败'));
            }
          };
          setTimeout(checkConnection, 100);
        }
        return;
      }

      try {
        console.log('正在连接WebSocket:', this.url);
        this.socket = new WebSocket(this.url);

        console.log('WebSocket对象已创建，等待连接建立...');

        // 设置连接超时
        const connectionTimeout = setTimeout(() => {
          if (this.socket && this.socket.readyState !== WebSocket.OPEN) {
            console.error('WebSocket连接超时');
            this.socket.close();
            globalWebSocketState = WebSocketConnectionState.ERROR;
            this.connectionState = WebSocketConnectionState.ERROR;
            globalWebSocketError = '连接超时，请稍后再试';
            reject(new Error('WebSocket连接超时'));
          }
        }, 10000); // 10秒超时

        // 连接打开事件
        this.socket.onopen = (event) => {
          clearTimeout(connectionTimeout);
          this.handleOpen(event);
          globalWebSocketState = WebSocketConnectionState.CONNECTED;
          this.connectionState = WebSocketConnectionState.CONNECTED;
          globalWebSocketError = null; // 清除错误信息
          resolve(true);
        };

        // 连接关闭事件
        this.socket.onclose = (event) => {
          clearTimeout(connectionTimeout);
          this.handleClose(event);
          reject(new Error('WebSocket连接已关闭'));
        };

        // 连接错误事件
        this.socket.onerror = (event) => {
          clearTimeout(connectionTimeout);
          this.handleError(event);
          reject(new Error('WebSocket连接错误'));
        };

        // 消息事件
        this.socket.onmessage = (event) => {
          this.handleMessage(event);
        };
      } catch (error) {
        console.error('WebSocket连接创建错误:', error);
        globalWebSocketState = WebSocketConnectionState.ERROR;
        this.connectionState = WebSocketConnectionState.ERROR;
        globalWebSocketError = '无法创建WebSocket连接';
        this.notifyError(new Error(`WebSocket连接失败: ${error}`));
        this.attemptReconnect();
        reject(error);
      }
    });
  }

  /**
   * 关闭WebSocket连接
   */
  public disconnect(): void {
    // 停止心跳检测
    this.stopHeartbeat();

    if (this.socket) {
      console.log('关闭WebSocket连接');
      this.socket.close();
      this.socket = null;
    }

    this.isConnected = false;
    this.connectionId = null;

    // 清除重连计时器
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }

    // 更新状态
    globalWebSocketState = WebSocketConnectionState.DISCONNECTED;
    this.connectionState = WebSocketConnectionState.DISCONNECTED;
  }

  /**
   * 发送消息
   *
   * @param message 消息内容
   * @returns Promise对象，表示消息是否发送成功
   */
  public async sendMessage(message: any): Promise<boolean> {
    if (!this.isConnected) {
      console.log('WebSocket未连接，正在连接...');
      try {
        // 等待连接建立
        const connected = await this.connect();
        if (!connected) {
          this.notifyError(new Error('无法连接到WebSocket服务器'));
          return false;
        }
      } catch (error) {
        console.error('WebSocket连接失败:', error);
        this.notifyError(new Error(`无法连接到WebSocket服务器: ${error}`));
        return false;
      }
    }

    try {
      console.log('发送消息到WebSocket:', message);
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify(message));
        return true;
      } else {
        const errorMsg = 'WebSocket未就绪，无法发送消息';
        console.error(errorMsg, this.socket ? `状态: ${this.socket.readyState}` : '无连接');
        this.notifyError(new Error(errorMsg));
        return false;
      }
    } catch (error) {
      console.error('发送消息错误:', error);
      this.notifyError(new Error(`发送消息失败: ${error}`));
      return false;
    }
  }

  /**
   * 发送查询
   *
   * @param query 查询字符串
   * @param connectionId 数据库连接ID
   * @returns Promise对象，表示查询是否发送成功
   */
  public async sendQuery(query: string, connectionId?: number): Promise<boolean> {
    const message = {
      query: query,
      ...(connectionId !== undefined && { connectionId })
    };

    return this.sendMessage(message);
  }

  /**
   * 发送反馈
   *
   * @param content 反馈内容
   * @returns Promise对象，表示反馈是否发送成功
   */
  public async sendFeedback(content: string): Promise<boolean> {
    const message = {
      content: content,
      source: "user",
      type: "text",
      role: "user",
      is_feedback: true
    };

    return this.sendMessage(message);
  }

  /**
   * 发送心跳消息
   */
  private sendHeartbeat(): void {
    this.sendMessage({
      type: "heartbeat",
      timestamp: new Date().toISOString()
    }).then((success) => {
      if (success) {
        // 设置下一次心跳
        this.heartbeatTimeoutId = setTimeout(() => {
          this.sendHeartbeat();
        }, this.heartbeatInterval);
      } else {
        // 如果发送失败，尝试重连
        this.attemptReconnect();
      }
    }).catch(() => {
      // 如果发送失败，尝试重连
      this.attemptReconnect();
    });
  }

  /**
   * 处理WebSocket连接打开
   */
  private handleOpen(event: Event): void {
    console.log('WebSocket连接已打开:', event);
    this.isConnected = true;
    this.reconnectAttempts = 0;
    this.backendAvailable = true; // 重置后端可用状态

    // 启动心跳检测
    this.startHeartbeat();

    // 触发连接事件
    this.emit('connected');
  }

  /**
   * 处理WebSocket连接关闭
   */
  private handleClose(event: CloseEvent): void {
    console.log('WebSocket连接已关闭:', event);
    this.isConnected = false;

    // 停止心跳检测
    this.stopHeartbeat();

    // 尝试重连
    this.attemptReconnect();

    // 触发断开连接事件
    this.emit('disconnected', event.reason);
  }

  /**
   * 处理WebSocket连接错误
   */
  private handleError(event: Event): void {
    const now = Date.now();

    // 防抖处理，避免频繁显示错误
    if (now - lastErrorTimestamp > ERROR_DEBOUNCE_MS) {
      lastErrorTimestamp = now;

      console.error('WebSocket连接错误:', event);
      globalWebSocketState = WebSocketConnectionState.ERROR;
      this.connectionState = WebSocketConnectionState.ERROR;
      globalWebSocketError = '连接服务器时出错，请稍后再试';

      // 标记后端可能不可用
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        this.backendAvailable = false;
        globalWebSocketError = '无法连接到服务器，请检查网络连接或联系管理员';
      }

      // 触发错误事件
      this.emit('error', new Error('WebSocket连接错误'));
    }

    // 尝试重连
    this.attemptReconnect();
  }

  /**
   * 处理WebSocket消息
   */
  private handleMessage(event: MessageEvent): void {
    try {
      // 解析消息
      const message = JSON.parse(event.data);

      // 处理系统消息
      if (message.type === 'system' && message.connection_id) {
        this.connectionId = message.connection_id;
        console.log('已获取连接ID:', this.connectionId);
      }

      // 处理心跳响应
      if (message.type === 'heartbeat_response') {
        console.log('收到心跳响应:', message);
        return;
      }

      // 根据消息类型分发
      if (message.type && this.messageHandlers.has(message.type)) {
        const handler = this.messageHandlers.get(message.type);
        if (handler) {
          handler(message);
        }
      }

      // 触发消息事件
      this.emit('message', message);

      // 触发特定类型的消息事件
      if (message.type) {
        this.emit(`message:${message.type}`, message);
      }

      // 触发特定区域的消息事件
      if (message.region) {
        this.emit(`message:region:${message.region}`, message);
      }
    } catch (error) {
      console.error('处理WebSocket消息错误:', error, '原始消息:', event.data);
      this.notifyError(new Error(`处理WebSocket消息错误: ${error}`));
    }
  }

  /**
   * 尝试重新连接
   */
  private attemptReconnect(): void {
    // 如果已经在重连中，不再重复执行
    if (this.reconnectTimeoutId) {
      return;
    }

    // 如果超过最大重连次数，不再重连
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log(`已达到最大重连次数(${this.maxReconnectAttempts})，不再重连`);
      globalWebSocketState = WebSocketConnectionState.ERROR;
      this.connectionState = WebSocketConnectionState.ERROR;
      globalWebSocketError = '无法连接到服务器，请检查网络连接或联系管理员';

      // 标记后端可能不可用
      this.backendAvailable = false;

      // 触发重连失败事件
      this.emit('reconnect_failed');
      return;
    }

    // 更新状态
    globalWebSocketState = WebSocketConnectionState.RECONNECTING;
    this.connectionState = WebSocketConnectionState.RECONNECTING;

    // 增加重连次数
    this.reconnectAttempts++;

    // 计算重连延迟（指数退避）
    const delay = Math.min(30000, this.reconnectTimeout * Math.pow(1.5, this.reconnectAttempts - 1));

    console.log(`计划在 ${delay}ms 后进行第 ${this.reconnectAttempts} 次重连尝试`);

    // 设置重连计时器
    this.reconnectTimeoutId = setTimeout(() => {
      console.log(`正在进行第 ${this.reconnectAttempts} 次重连尝试`);
      this.reconnectTimeoutId = null;

      // 触发重连事件
      this.emit('reconnecting', this.reconnectAttempts);

      // 尝试重新连接
      this.connect().then(() => {
        console.log('重连成功');

        // 触发重连成功事件
        this.emit('reconnected');
      }).catch((error) => {
        console.error('重连失败:', error);

        // 继续尝试重连
        this.attemptReconnect();
      });
    }, delay);
  }

  /**
   * 启动心跳检测
   */
  private startHeartbeat(): void {
    // 清除现有心跳
    this.stopHeartbeat();

    // 设置新的心跳
    this.heartbeatTimeoutId = setTimeout(() => {
      this.sendHeartbeat();
    }, this.heartbeatInterval);
  }

  /**
   * 停止心跳检测
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimeoutId) {
      clearTimeout(this.heartbeatTimeoutId);
      this.heartbeatTimeoutId = null;
    }
  }

  /**
   * 通知错误
   */
  private notifyError(error: Error): void {
    // 触发错误事件
    this.emit('error', error);
  }

  /**
   * 注册消息处理器
   *
   * @param type 消息类型
   * @param handler 处理函数
   */
  public registerMessageHandler(type: string, handler: (message: any) => void): void {
    this.messageHandlers.set(type, handler);
  }

  /**
   * 取消注册消息处理器
   *
   * @param type 消息类型
   */
  public unregisterMessageHandler(type: string): void {
    this.messageHandlers.delete(type);
  }

  /**
   * 获取连接状态
   */
  public getConnectionState(): WebSocketConnectionState {
    return this.connectionState;
  }

  /**
   * 获取连接ID
   */
  public getConnectionId(): string | null {
    return this.connectionId;
  }

  /**
   * 获取用户ID
   */
  public getUserId(): string | null {
    return this.userId;
  }

  /**
   * 设置用户ID
   *
   * @param userId 用户ID
   */
  public setUserId(userId: string): void {
    this.userId = userId;
  }
}

// 创建全局WebSocket管理器实例
let webSocketManagerInstance: WebSocketManager | null = null;

/**
 * 获取WebSocket管理器实例
 *
 * @param userId 可选的用户ID
 */
export const getWebSocketManager = (userId?: string): WebSocketManager => {
  if (!webSocketManagerInstance) {
    webSocketManagerInstance = new WebSocketManager(userId);
  } else if (userId && webSocketManagerInstance.getUserId() !== userId) {
    // 如果用户ID变化，更新用户ID
    webSocketManagerInstance.setUserId(userId);
  }

  return webSocketManagerInstance;
};
