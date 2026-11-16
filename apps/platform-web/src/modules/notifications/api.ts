import { platformHttpClient } from "@/services/http/client";
import type {
  CreateChannelRequest,
  NotificationChannelItem,
  NotificationLevel,
  NotificationPage,
  NotificationStatus,
  TestChannelResponse,
  UnreadCountResponse,
  UpdateChannelRequest,
} from "./types";

export interface ListNotificationsParams {
  limit?: number;
  offset?: number;
  status?: NotificationStatus;
  level?: NotificationLevel;
  project_id?: string;
}

export async function fetchNotifications(
  params?: ListNotificationsParams,
): Promise<NotificationPage> {
  const resp = await platformHttpClient.get<NotificationPage>(
    "/api/notifications",
    { params },
  );
  return resp.data;
}

export async function fetchUnreadCount(): Promise<number> {
  const resp = await platformHttpClient.get<UnreadCountResponse>(
    "/api/notifications/unread-count",
  );
  return resp.data.unread_count;
}

export async function markNotificationRead(id: string): Promise<void> {
  await platformHttpClient.patch(`/api/notifications/${id}/read`);
}

export async function markAllNotificationsRead(): Promise<number> {
  const resp = await platformHttpClient.post<{ updated_count: number }>(
    "/api/notifications/mark-all-read",
  );
  return resp.data.updated_count;
}

export async function fetchChannels(params?: {
  project_id?: string;
  enabled_only?: boolean;
}): Promise<NotificationChannelItem[]> {
  const resp = await platformHttpClient.get<NotificationChannelItem[]>(
    "/api/notifications/channels",
    { params },
  );
  return resp.data;
}

export async function createChannel(
  data: CreateChannelRequest,
): Promise<NotificationChannelItem> {
  const resp = await platformHttpClient.post<NotificationChannelItem>(
    "/api/notifications/channels",
    data,
  );
  return resp.data;
}

export async function updateChannel(
  id: string,
  data: UpdateChannelRequest,
): Promise<NotificationChannelItem> {
  const resp = await platformHttpClient.patch<NotificationChannelItem>(
    `/api/notifications/channels/${id}`,
    data,
  );
  return resp.data;
}

export async function deleteChannel(id: string): Promise<void> {
  await platformHttpClient.delete(`/api/notifications/channels/${id}`);
}

export async function testChannel(id: string): Promise<TestChannelResponse> {
  const resp = await platformHttpClient.post<TestChannelResponse>(
    `/api/notifications/channels/${id}/test`,
  );
  return resp.data;
}
