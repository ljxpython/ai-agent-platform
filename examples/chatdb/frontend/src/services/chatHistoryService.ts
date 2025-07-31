import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

// 创建API实例
const api = axios.create({
  baseURL: API_BASE_URL,
});

// 聊天历史接口类型定义
export interface ChatHistoryResponse {
  id: string;
  title: string;
  timestamp: string;
  query: string;
  response: {
    analysis: string;
    sql: string;
    explanation: string;
    data: any[];
    visualization: any;
  };
  connection_id?: number | null;
}

export interface ChatHistoryListResponse {
  sessions: ChatHistoryResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface SaveChatHistoryRequest {
  session_id: string;
  title: string;
  query: string;
  response: {
    analysis: string;
    sql: string;
    explanation: string;
    data: any[];
    visualization: any;
  };
  connection_id?: number | null;
}

export interface RestoreChatHistoryResponse {
  session_id: string;
  title: string;
  query: string;
  response: {
    analysis: string;
    sql: string;
    explanation: string;
    data: any[];
    visualization: any;
  };
  connection_id?: number | null;
  created_at: string;
}

// 聊天历史服务类
export class ChatHistoryService {
  /**
   * 获取聊天历史列表
   */
  async getChatHistories(
    skip: number = 0,
    limit: number = 50,
    connectionId?: number
  ): Promise<ChatHistoryListResponse> {
    try {
      const params: any = { skip, limit };
      if (connectionId !== undefined) {
        params.connection_id = connectionId;
      }

      const response = await api.get('/chat-history/', { params });
      return response.data;
    } catch (error) {
      console.error('获取聊天历史失败:', error);
      throw error;
    }
  }

  /**
   * 保存聊天历史
   */
  async saveChatHistory(request: SaveChatHistoryRequest): Promise<{ status: string; message: string }> {
    try {
      const response = await api.post('/chat-history/save', request);
      return response.data;
    } catch (error) {
      console.error('保存聊天历史失败:', error);
      throw error;
    }
  }

  /**
   * 通过SSE端点保存聊天历史
   */
  async saveChatHistoryViaSSE(request: SaveChatHistoryRequest): Promise<{ status: string; message: string }> {
    try {
      const response = await api.post('/text2sql-sse/save-history', request);
      return response.data;
    } catch (error) {
      console.error('通过SSE保存聊天历史失败:', error);
      throw error;
    }
  }

  /**
   * 获取指定会话的聊天历史
   */
  async getChatHistory(sessionId: string): Promise<RestoreChatHistoryResponse> {
    try {
      const response = await api.get(`/chat-history/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('获取聊天历史失败:', error);
      throw error;
    }
  }

  /**
   * 删除聊天历史
   */
  async deleteChatHistory(sessionId: string): Promise<{ status: string; message: string }> {
    try {
      const response = await api.delete(`/chat-history/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('删除聊天历史失败:', error);
      throw error;
    }
  }

  /**
   * 恢复聊天历史
   */
  async restoreChatHistory(sessionId: string): Promise<{ status: string; message: string }> {
    try {
      const response = await api.post(`/chat-history/${sessionId}/restore`);
      return response.data;
    } catch (error) {
      console.error('恢复聊天历史失败:', error);
      throw error;
    }
  }
}

// 创建服务实例
export const chatHistoryService = new ChatHistoryService();

// 导出默认实例
export default chatHistoryService;
