// Text2SQL API 响应类型定义
export interface Text2SQLResponse {
  sql: string;
  explanation: string;
  results: any[];
  visualization_type: string;
  visualization_config: any;
}

// Text2SQL 请求类型定义
export interface Text2SQLRequest {
  query: string;
}
