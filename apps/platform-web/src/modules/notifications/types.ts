export type NotificationLevel = "info" | "warning" | "error" | "critical";

export type NotificationCategory = "agent_run" | "budget" | "eval" | "system";

export type NotificationStatus = "unread" | "read" | "archived";

export type ChannelType =
  | "feishu"
  | "dingtalk"
  | "wechat"
  | "email"
  | "webhook";

export interface NotificationItem {
  id: string;
  recipient_user_id: string | null;
  project_id: string | null;
  title: string;
  content: string;
  level: NotificationLevel;
  category: NotificationCategory;
  status: NotificationStatus;
  action_url: string | null;
  extra_metadata: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
}

export interface NotificationPage {
  items: NotificationItem[];
  total: number;
  unread_count: number;
  limit: number;
  offset: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface NotificationChannelItem {
  id: string;
  name: string;
  project_ids: string[];
  channel_type: ChannelType;
  endpoint_url: string;
  secret_token: string | null;
  is_enabled: boolean;
  subscribed_events: string[];
  created_at: string;
  updated_at: string;
}

export interface CreateChannelRequest {
  name: string;
  project_ids?: string[];
  channel_type: ChannelType;
  endpoint_url: string;
  secret_token?: string | null;
  is_enabled?: boolean;
  subscribed_events?: string[];
}

export interface UpdateChannelRequest {
  name?: string;
  project_ids?: string[];
  endpoint_url?: string;
  secret_token?: string | null;
  is_enabled?: boolean;
  subscribed_events?: string[];
}

export interface TestChannelResponse {
  success: boolean;
  channel_id: string;
  channel_name: string;
  message: string;
}
