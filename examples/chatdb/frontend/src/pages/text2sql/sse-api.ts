import { Text2SQLResponse } from './types';
import axios from 'axios';

// API基础URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// 流式响应消息
export interface StreamResponseMessage {
  source: string;
  content: string;
  is_final?: boolean;
  region?: string;
  type?: string;
  message_id?: string;
  timestamp?: string;
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

// SSE连接状态枚举
export enum SSEConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error'
}

// 全局SSE状态
export let globalSSEState: SSEConnectionState = SSEConnectionState.DISCONNECTED;
export let globalSSEError: string | null = null;

// 活动会话
let activeEventSource: EventSource | null = null;
let activeSessionId: string | null = null;

// 处理SSE错误的防抖
let lastErrorTimestamp = 0;
const ERROR_DEBOUNCE_MS = 5000; // 5秒内不重复显示相同错误

/**
 * 关闭SSE连接
 */
export const closeSSEConnection = (): void => {
  if (activeEventSource) {
    console.log('关闭SSE连接');
    activeEventSource.close();
    activeEventSource = null;
    activeSessionId = null;
    globalSSEState = SSEConnectionState.DISCONNECTED;
  }
};

/**
 * 发送Text2SQL请求并通过SSE接收响应
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
): string => {
  // 关闭现有连接
  closeSSEConnection();

  // 构建SSE URL
  let sseUrl = `${API_BASE_URL}/text2sql-sse/stream?query=${encodeURIComponent(query)}&direct_process=true`;
  if (connectionId !== undefined) {
    sseUrl += `&connection_id=${connectionId}`;
  }

  console.log('开始SSE请求:', sseUrl);
  console.log('请求参数: query=', query, 'connectionId=', connectionId);
  console.log('API_BASE_URL:', API_BASE_URL);

  try {
    // 更新全局状态
    globalSSEState = SSEConnectionState.CONNECTING;
    globalSSEError = null;

    // 创建EventSource
    const eventSource = new EventSource(sseUrl);
    activeEventSource = eventSource;

    // 连接打开
    eventSource.onopen = (event) => {
      console.log('SSE连接已打开', event);
      globalSSEState = SSEConnectionState.CONNECTED;
    };

    // 添加默认消息处理程序，确保所有消息都能被处理
    eventSource.onmessage = (event) => {
      try {
        console.log('收到默认消息:', event.data);

        // 尝试解析JSON
        try {
          const data = JSON.parse(event.data);
          console.log('解析后的消息数据:', data);

          // 检查是否有内容字段
          if (data.content) {
            // 如果有内容，直接使用
            onMessage(data);
          } else if (typeof data === 'string') {
            // 如果是字符串，作为内容传递
            onMessage({
              type: 'message',
              source: '系统',
              content: data,
              region: 'analysis'
            });
          } else {
            // 如果是其他对象，尝试提取有用信息
            let content = '';
            if (data.message) content = data.message;
            else if (data.result) content = JSON.stringify(data.result);
            else content = JSON.stringify(data);

            onMessage({
              type: 'message',
              source: '系统',
              content: content,
              region: 'analysis'
            });
          }
        } catch (parseError) {
          // 如果不是JSON，尝试直接使用原始文本
          console.log('非JSON消息，直接使用原始文本:', event.data);
          onMessage({
            type: 'message',
            source: '系统',
            content: event.data,
            region: 'analysis' // 强制显示在分析区域
          });
        }
      } catch (e) {
        console.error('处理默认消息失败:', e, '原始消息:', event.data);
        // 即使出错，也尝试将原始消息显示出来
        try {
          onMessage({
            type: 'message',
            source: '系统',
            content: `收到消息: ${event.data}`,
            region: 'analysis'
          });
        } catch (finalError) {
          console.error('最终尝试处理消息失败:', finalError);
        }
      }
    };

    // 会话事件 - 获取会话ID
    eventSource.addEventListener('session', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        activeSessionId = data.session_id;
        console.log('已建立会话:', activeSessionId);
      } catch (e) {
        console.error('解析会话信息失败:', e);
      }
    });

    // 消息事件
    eventSource.addEventListener('message', (event: MessageEvent) => {
      try {
        console.log('收到message事件消息:', event.data);
        const data = JSON.parse(event.data);

        // 记录消息类型和区域
        console.log(`消息类型: ${data.type || 'unknown'}, 区域: ${data.region || 'unknown'}, 最终: ${data.is_final ? 'true' : 'false'}`);

        // 处理消息 - 即使没有region或type也尝试处理
        try {
          onMessage(data);
          console.log('消息已处理:', data);
        } catch (messageError) {
          console.error('处理消息时出错:', messageError);
        }

        // 处理特定类型的最终结果
        if (data.is_final) {
          console.log(`处理最终消息: 区域=${data.region}`);

          if (data.region === 'sql' && onFinalSql) {
            console.log('处理最终SQL结果:', data.content);
            onFinalSql(data.content);
          } else if (data.region === 'explanation' && onFinalExplanation) {
            console.log('处理最终解释结果');
            onFinalExplanation(data.content);
          } else if (data.region === 'data' && onFinalData) {
            console.log('处理最终数据结果');
            try {
              const results = JSON.parse(data.content);
              onFinalData(results);
            } catch (e) {
              console.error('解析数据结果失败:', e);
            }
          } else if (data.region === 'visualization' && onFinalVisualization) {
            console.log('处理最终可视化结果');
            try {
              const visualizationData = JSON.parse(data.content);
              onFinalVisualization(visualizationData);
            } catch (e) {
              console.error('解析可视化数据失败:', e);
            }
          }
        }
      } catch (e) {
        console.error('解析消息失败:', e, '原始消息:', event.data);
        // 尝试将原始消息作为纯文本处理
        try {
          onMessage({
            type: 'message',
            source: '系统',
            content: event.data,
            region: 'process'
          });
        } catch (fallbackError) {
          console.error('尝试将原始消息作为纯文本处理失败:', fallbackError);
        }
      }
    });

    // 最终结果事件
    eventSource.addEventListener('final_result', (event: MessageEvent) => {
      try {
        console.log('收到最终结果:', event.data);
        const data = JSON.parse(event.data);

        // 处理最终结果
        if (data.result) {
          onResult(data.result);
        }

        // 关闭连接
        console.log('处理完成，关闭SSE连接');
        eventSource.close();
        activeEventSource = null;
        globalSSEState = SSEConnectionState.DISCONNECTED;
      } catch (e) {
        console.error('解析最终结果失败:', e);
        onError(new Error(`解析最终结果失败: ${e}`));
      }
    });

    // 错误事件
    eventSource.onerror = (event) => {
      const now = Date.now();
      // 防抖处理，避免频繁显示错误
      if (now - lastErrorTimestamp > ERROR_DEBOUNCE_MS) {
        lastErrorTimestamp = now;

        console.error('SSE连接错误:', event);
        globalSSEState = SSEConnectionState.ERROR;
        globalSSEError = '连接服务器时出错，请稍后再试';

        onError(new Error('SSE连接错误'));
      }

      // 关闭连接
      eventSource.close();
      activeEventSource = null;
    };

    // 关闭事件
    eventSource.addEventListener('close', () => {
      console.log('SSE连接已关闭');
      eventSource.close();
      activeEventSource = null;
      globalSSEState = SSEConnectionState.DISCONNECTED;
    });

    // 返回会话ID（如果还没有分配，返回临时ID）
    return activeSessionId || 'pending';

  } catch (error) {
    console.error('创建SSE连接失败:', error);
    globalSSEState = SSEConnectionState.ERROR;
    globalSSEError = '无法连接到服务器';
    onError(error instanceof Error ? error : new Error(String(error)));
    return '';
  }
};

/**
 * 发送用户反馈
 */
export const sendUserFeedback = async (
  sessionId: string,
  feedback: string,
  onError: (error: Error) => void
): Promise<boolean> => {
  if (!sessionId) {
    console.error('无法发送反馈：会话ID不存在');
    onError(new Error('无法发送反馈：会话ID不存在'));
    return false;
  }

  try {
    console.log(`发送反馈到会话 ${sessionId}:`, feedback);

    const response = await axios.post(
      `${API_BASE_URL}/text2sql-sse/feedback/${sessionId}`,
      { content: feedback, source: 'user' }
    );

    if (response.status === 200) {
      console.log('反馈发送成功:', response.data);
      return true;
    } else {
      console.error('发送反馈失败:', response.status, response.data);
      onError(new Error(`发送反馈失败: ${response.status}`));
      return false;
    }
  } catch (error) {
    console.error('发送反馈出错:', error);
    onError(error instanceof Error ? error : new Error(String(error)));
    return false;
  }
};

/**
 * 发送用户同意操作
 */
export const sendUserApproval = async (
  sessionId: string,
  onError: (error: Error) => void
): Promise<boolean> => {
  return sendUserFeedback(sessionId, 'APPROVE', onError);
};

/**
 * 获取会话信息
 */
export const getSessionInfo = async (
  sessionId: string
): Promise<any> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/text2sql-sse/sessions/${sessionId}`);
    return response.data;
  } catch (error) {
    console.error('获取会话信息失败:', error);
    throw error;
  }
};

/**
 * 列出所有活动会话
 */
export const listSessions = async (): Promise<any> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/text2sql-sse/sessions`);
    return response.data;
  } catch (error) {
    console.error('获取会话列表失败:', error);
    throw error;
  }
};

/**
 * 删除会话
 */
export const deleteSession = async (
  sessionId: string
): Promise<boolean> => {
  try {
    const response = await axios.delete(`${API_BASE_URL}/text2sql-sse/sessions/${sessionId}`);
    return response.status === 200;
  } catch (error) {
    console.error('删除会话失败:', error);
    return false;
  }
};
