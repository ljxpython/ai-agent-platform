// 共享的聊天相关类型定义

// 数据库连接类型
export interface Connection {
  id: number;
  name: string;
  type: string;
  host: string;
  port: number;
  username: string;
  database: string;
  created_at: string;
  updated_at: string;
}

// 聊天历史记录类型
export interface ChatHistory {
  id: string;
  title: string;
  timestamp: Date;
  query: string;
  response: {
    analysis: string;
    sql: string;
    explanation: string;
    data: any[];
    visualization: any;
  };
  connectionId: number | null;
}

// 时间轴消息类型
export interface TimelineMessage {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  status: 'sending' | 'sent' | 'streaming' | 'completed' | 'error';
  metadata?: {
    region?: string;
    source?: string;
    isSQL?: boolean;
    isVisualization?: boolean;
  };
}

// 聊天历史侧边栏Props
export interface ChatHistorySidebarProps {
  histories: ChatHistory[];
  selectedHistoryId: string | null;
  onSelectHistory: (historyId: string) => void;
  onDeleteHistory: (historyId: string) => void;
  onNewChat: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

// 连接选择器Props
export interface ConnectionSelectorProps {
  connections: Connection[];
  selectedConnectionId: number | null;
  onConnectionChange: (connectionId: number) => void;
  loading?: boolean;
}

// 时间轴聊天Props
export interface TimelineChatProps {
  messages: TimelineMessage[];
  isStreaming: boolean;
  connections?: Connection[];
  selectedConnectionId?: number | null;
  onConnectionChange?: (connectionId: number) => void;
  loadingConnections?: boolean;
}
