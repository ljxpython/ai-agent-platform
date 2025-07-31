// API相关类型定义

export interface DBConnection {
  id: number;
  name: string;
  db_type: string;
  host: string;
  port: number;
  username: string;
  database_name: string;
  created_at: string;
  updated_at: string;
}

export interface SchemaTable {
  id: number;
  connection_id: number;
  table_name: string;
  description?: string;
  ui_metadata?: any;
  created_at: string;
  updated_at: string;
  columns?: SchemaColumn[];
}

export interface SchemaColumn {
  id: number;
  table_id: number;
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  column_default?: string;
  description?: string;
  ui_metadata?: any;
  created_at: string;
  updated_at: string;
  value_mappings?: ValueMapping[];
}

export interface ValueMapping {
  id: number;
  column_id: number;
  nl_term: string;
  db_value: string;
  created_at: string;
  updated_at: string;
}

export interface SchemaRelationship {
  id: number;
  connection_id: number;
  source_table_id: number;
  source_column_id: number;
  target_table_id: number;
  target_column_id: number;
  relationship_type?: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface QueryResult {
  sql: string;
  results: any[];
  error?: string;
  context?: any;
}

export interface APIResponse<T = any> {
  data: T;
  message?: string;
  status?: string;
}

export interface ConnectionCreateRequest {
  name: string;
  db_type: string;
  host: string;
  port: number;
  username: string;
  password: string;
  database_name: string;
}

export interface ConnectionUpdateRequest {
  name?: string;
  db_type?: string;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  database_name?: string;
}

export interface ValueMappingCreateRequest {
  column_id: number;
  nl_term: string;
  db_value: string;
}

export interface ValueMappingUpdateRequest {
  nl_term?: string;
  db_value?: string;
}

export interface TableUpdateRequest {
  table_name?: string;
  description?: string;
  ui_metadata?: any;
}

export interface ColumnUpdateRequest {
  column_name?: string;
  data_type?: string;
  is_nullable?: boolean;
  column_default?: string;
  description?: string;
  ui_metadata?: any;
}

export interface SchemaDiscoveryRequest {
  connection_id: number;
}

export interface SchemaDiscoveryResponse {
  tables: SchemaTable[];
  relationships: SchemaRelationship[];
  message: string;
}

export interface GraphVisualizationData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  type?: string;
  properties?: Record<string, any>;
}

export interface TestConnectionRequest {
  connection_id: number;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  error?: string;
}

export interface ExecuteQueryRequest {
  connection_id: number;
  query: string;
}

export interface ExecuteQueryResponse {
  results: any[];
  columns: string[];
  row_count: number;
  execution_time_ms: number;
  error?: string;
}

// 错误响应类型
export interface APIError {
  detail: string;
  status_code: number;
  error_type?: string;
}

// 分页响应类型
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// 统计信息类型
export interface ConnectionStats {
  total_connections: number;
  active_connections: number;
  total_tables: number;
  total_columns: number;
  total_relationships: number;
  total_value_mappings: number;
}

// 健康检查响应
export interface HealthCheckResponse {
  status: string;
  timestamp: string;
  version?: string;
  database_status?: string;
  services?: Record<string, string>;
}

// 导出/导入相关类型
export interface ExportRequest {
  connection_id: number;
  format: 'json' | 'csv' | 'sql';
  include_data?: boolean;
}

export interface ImportRequest {
  connection_id: number;
  file_content: string;
  format: 'json' | 'csv' | 'sql';
  overwrite?: boolean;
}

// 批量操作类型
export interface BatchOperationRequest<T> {
  items: T[];
  operation: 'create' | 'update' | 'delete';
}

export interface BatchOperationResponse {
  success_count: number;
  error_count: number;
  errors: string[];
  results: any[];
}
