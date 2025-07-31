// 混合问答对服务

import axios from 'axios';
import type { SimilarQAPair, QAPairCreate, SearchRequest, FeedbackRequest } from '../types/hybridQA';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const hybridQAService = {
  // 创建问答对
  async createQAPair(data: QAPairCreate): Promise<{ status: string; qa_id: string; message: string }> {
    const response = await api.post('/hybrid-qa/qa-pairs/', data);
    return response.data;
  },

  // 批量创建问答对
  async batchCreateQAPairs(data: QAPairCreate[]): Promise<{
    status: string;
    created_count: number;
    failed_count: number;
    errors: string[];
  }> {
    const response = await api.post('/hybrid-qa/qa-pairs/batch-create', data);
    return response.data;
  },

  // 搜索相似问答对
  async searchSimilar(data: SearchRequest): Promise<SimilarQAPair[]> {
    const response = await api.post('/hybrid-qa/qa-pairs/search', data);
    return response.data;
  },

  // 获取统计信息
  async getStats(connectionId?: number): Promise<{
    total_qa_pairs: number;
    verified_qa_pairs: number;
    query_types: Record<string, number>;
    difficulty_distribution: Record<string, number>;
    average_success_rate: number;
  }> {
    const params = connectionId ? { connection_id: connectionId } : {};
    const response = await api.get('/hybrid-qa/qa-pairs/stats', { params });
    return response.data;
  },

  // 提交反馈
  async submitFeedback(data: FeedbackRequest): Promise<{ status: string; message: string }> {
    const response = await api.post('/hybrid-qa/qa-pairs/feedback', data);
    return response.data;
  },

  // 删除问答对
  async deleteQAPair(qaId: string): Promise<{ status: string; message: string }> {
    const response = await api.delete(`/hybrid-qa/qa-pairs/${qaId}`);
    return response.data;
  },

  // 导出问答对
  async exportQAPairs(connectionId?: number, format: string = 'json'): Promise<{
    status: string;
    message: string;
    format: string;
    connection_id?: number;
  }> {
    const params = { format, ...(connectionId && { connection_id: connectionId }) };
    const response = await api.get('/hybrid-qa/qa-pairs/export', { params });
    return response.data;
  },

  // 健康检查
  async healthCheck(): Promise<{
    status: string;
    services?: Record<string, string>;
    error?: string;
    timestamp: string;
  }> {
    const response = await api.get('/hybrid-qa/qa-pairs/health');
    return response.data;
  },

  // 获取推荐示例（用于Text2SQL页面）
  async getRecommendedExamples(
    question: string,
    connectionId?: number,
    schemaContext?: any,
    topK: number = 3
  ): Promise<SimilarQAPair[]> {
    const response = await api.post('/hybrid-qa/qa-pairs/search', {
      question,
      connection_id: connectionId,
      schema_context: schemaContext,
      top_k: topK
    });
    return response.data;
  }
};

// 混合检索增强的Text2SQL服务
export const enhancedText2SQLService = {
  // 增强的SQL生成（集成混合检索）
  async generateSQLWithExamples(data: {
    query: string;
    connection_id: number;
    schema_context?: any;
    use_hybrid_retrieval?: boolean;
  }): Promise<{
    sql: string;
    explanation: string;
    examples_used: number;
    confidence_score: number;
    similar_examples?: SimilarQAPair[];
  }> {
    // 首先获取相似示例
    let similarExamples: SimilarQAPair[] = [];
    if (data.use_hybrid_retrieval !== false) {
      try {
        similarExamples = await hybridQAService.getRecommendedExamples(
          data.query,
          data.connection_id,
          data.schema_context,
          3
        );
      } catch (error) {
        console.warn('获取相似示例失败，使用标准模式:', error);
      }
    }

    // 调用增强的Text2SQL API
    const response = await api.post('/text2sql/generate-enhanced', {
      ...data,
      similar_examples: similarExamples
    });

    return {
      ...response.data,
      similar_examples: similarExamples
    };
  },

  // 学习用户确认的问答对
  async learnFromUserConfirmation(data: {
    question: string;
    sql: string;
    connection_id: number;
    schema_context?: any;
    user_satisfaction: number;
  }): Promise<{ status: string; message: string }> {
    const response = await api.post('/hybrid-qa/qa-pairs/learn', data);
    return response.data;
  }
};
