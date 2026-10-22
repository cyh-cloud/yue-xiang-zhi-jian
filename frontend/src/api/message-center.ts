import { del, get, post } from "./client";

export type MessageSource =
  | "system_announcement"
  | "job_application"
  | "messages"
  | "notifications";

export interface SystemAnnouncement {
  id: number | string;
  title: string;
  content: string;
  created_at: string;
}

export interface JobApplication {
  id: number | string;
  title: string;
  company: string;
  location: string;
  status: string;
  applied_at: string;
  enterprise_id: string;
}

export interface InboxMessage {
  id: number | string;
  sender_id: string;
  receiver_id: string;
  content: string;
  is_read: number | boolean;
  created_at: string;
  other_id: string;
  other_name: string;
  is_mine: boolean;
}

export interface SiteNotification {
  id: number | string;
  type: string;
  title: string;
  content: string;
  is_read: number | boolean;
  created_at: string;
}

export interface ConversationMessage {
  id: number | string;
  sender_id: string;
  receiver_id: string;
  content: string;
  is_read: number | boolean;
  created_at: string;
}

export interface ReadRefs {
  system_announcement: Array<number | string>;
  job_application: Array<number | string>;
}

export interface ReadState extends ReadRefs {
  dismissed: {
    system_announcement: Array<number | string>;
    job_application: Array<number | string>;
  };
}

interface UnreadResponse {
  success: true;
  count: number;
}

interface ReadStateResponse {
  success: true;
  refs: ReadRefs;
  dismissed: ReadState["dismissed"];
}

interface AnnouncementsResponse {
  success: true;
  announcements: SystemAnnouncement[];
}

interface ApplicationsResponse {
  success: true;
  applications: JobApplication[];
}

interface InboxResponse {
  success: true;
  inbox: InboxMessage[];
}

interface NotificationsResponse {
  success: true;
  notifications: SiteNotification[];
}

interface ConversationResponse {
  success: true;
  messages: ConversationMessage[];
}

interface SendMessageResponse {
  success: true;
  message: string;
  id: number | string;
}

export async function getUnreadCount(userId: string): Promise<number> {
  const response = await get<UnreadResponse>(
    `/api/notifications/unread?user_id=${encodeURIComponent(userId)}`,
  );
  return response.count;
}

export async function getReadState(userId: string): Promise<ReadState> {
  const response = await get<ReadStateResponse>(
    `/api/notifications/read-state?user_id=${encodeURIComponent(userId)}`,
  );
  return {
    ...response.refs,
    dismissed: response.dismissed,
  };
}

export async function getSystemAnnouncements(): Promise<SystemAnnouncement[]> {
  const response = await get<AnnouncementsResponse>("/api/system-announcements");
  return response.announcements;
}

export async function getJobApplications(userId: string): Promise<JobApplication[]> {
  const response = await get<ApplicationsResponse>(
    `/api/employment/applications/${encodeURIComponent(userId)}`,
  );
  return response.applications;
}

export async function getInbox(userId: string): Promise<InboxMessage[]> {
  const response = await get<InboxResponse>(
    `/api/messages/inbox?user_id=${encodeURIComponent(userId)}`,
  );
  return response.inbox;
}

export async function getNotifications(userId: string): Promise<SiteNotification[]> {
  const response = await get<NotificationsResponse>(
    `/api/notifications?user_id=${encodeURIComponent(userId)}&limit=200`,
  );
  return response.notifications;
}

export function markReadOne(
  userId: string,
  source: MessageSource,
  refId: string,
): Promise<unknown> {
  return post("/api/notifications/read-one", {
    user_id: userId,
    source,
    ref_id: refId,
  });
}

export function markAllRead(userId: string): Promise<unknown> {
  return post("/api/notifications/read", { user_id: userId });
}

export function clearReadNotifications(userId: string): Promise<unknown> {
  return del(
    `/api/notifications/clear?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function getConversation(
  otherId: string,
  userId: string,
): Promise<ConversationMessage[]> {
  const response = await get<ConversationResponse>(
    `/api/messages/conversation/${encodeURIComponent(otherId)}?user_id=${encodeURIComponent(userId)}`,
  );
  return response.messages;
}

export function sendMessage(
  receiverId: string,
  content: string,
): Promise<SendMessageResponse> {
  return post<SendMessageResponse>("/api/messages/send", {
    receiver_id: receiverId,
    content,
  });
}
