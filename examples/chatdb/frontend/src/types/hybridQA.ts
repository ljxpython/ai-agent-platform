// 混合问答对相关类型定义

export interface QAPair {
  id: string;
  question: string;
  sql: string;
  connection_id: number;
  difficulty_level: number;
  query_type: string;
  success_rate: number;
  verified: boolean;
  created_at: string;
  used_tables: string[];
  mentioned_entities: string[];
}

export interface QAPairCreate {
  question: string;
  sql: string;
  connection_id: number;
  difficulty_level?: number;
  query_type?: string;
  verified?: boolean;
  used_tables?: string[];
  mentioned_entities?: string[];
}

export interface SimilarQAPair {
  qa_pair: QAPair;
  semantic_score: number;
  structural_score: number;
  pattern_score: number;
  quality_score: number;
  final_score: number;
  explanation: string;
}

export interface SearchRequest {
  question: string;
  connection_id?: number;
  schema_context?: any;
  top_k?: number;
}

export interface FeedbackRequest {
  qa_id: string;
  user_satisfaction: number; // 0.0 - 1.0
  feedback_text?: string;
}

export interface QAStats {
  total_qa_pairs: number;
  verified_qa_pairs: number;
  query_types: Record<string, number>;
  difficulty_distribution: Record<string, number>;
  average_success_rate: number;
}

export interface HybridRetrievalConfig {
  enabled: boolean;
  semantic_weight: number;
  structural_weight: number;
  pattern_weight: number;
  quality_weight: number;
  max_examples_per_query: number;
  parallel_retrieval: boolean;
}

export interface EnhancedText2SQLResponse {
  sql: string;
  explanation: string;
  examples_used: number;
  confidence_score: number;
  similar_examples?: SimilarQAPair[];
  retrieval_time_ms?: number;
  generation_time_ms?: number;
}
