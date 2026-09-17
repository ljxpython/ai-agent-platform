import { platformHttpClient } from '@/services/http/client';
import type {
  TerminalInputAck,
  TerminalListResponse,
  TerminalOutput,
  TerminalSession,
} from '@/types/workspace';

export async function createTerminalSession(
  projectId: string,
  threadId: string,
  payload: {
    request_id: string;
    acknowledge_execution: true;
    rows?: number;
    cols?: number;
  },
  signal?: AbortSignal,
): Promise<TerminalSession> {
  const res = await platformHttpClient.post<TerminalSession>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/terminals`,
    payload,
    {
      headers: { 'x-project-id': projectId },
      signal,
    },
  );
  return res.data;
}

export async function listTerminalSessions(
  projectId: string,
  threadId: string,
  signal?: AbortSignal,
): Promise<TerminalListResponse> {
  const res = await platformHttpClient.get<TerminalListResponse>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/terminals`,
    {
      headers: { 'x-project-id': projectId },
      signal,
    },
  );
  return res.data;
}

export async function getTerminalOutput(
  projectId: string,
  threadId: string,
  terminalId: string,
  offset: number = 0,
  signal?: AbortSignal,
): Promise<TerminalOutput> {
  const res = await platformHttpClient.get<TerminalOutput>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/terminals/${encodeURIComponent(terminalId)}/output`,
    {
      params: { offset },
      headers: { 'x-project-id': projectId },
      signal,
    },
  );
  return res.data;
}

export async function sendTerminalInput(
  projectId: string,
  threadId: string,
  terminalId: string,
  payload: {
    sequence: number;
    data_base64: string;
  },
  signal?: AbortSignal,
): Promise<TerminalInputAck> {
  const res = await platformHttpClient.post<TerminalInputAck>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/terminals/${encodeURIComponent(terminalId)}/input`,
    payload,
    {
      headers: { 'x-project-id': projectId },
      signal,
    },
  );
  return res.data;
}

export async function resizeTerminal(
  projectId: string,
  threadId: string,
  terminalId: string,
  payload: {
    rows: number;
    cols: number;
  },
  signal?: AbortSignal,
): Promise<TerminalSession> {
  const res = await platformHttpClient.post<TerminalSession>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/terminals/${encodeURIComponent(terminalId)}/resize`,
    payload,
    {
      headers: { 'x-project-id': projectId },
      signal,
    },
  );
  return res.data;
}

export async function closeTerminalSession(
  projectId: string,
  threadId: string,
  terminalId: string,
  signal?: AbortSignal,
): Promise<TerminalSession> {
  const res = await platformHttpClient.delete<TerminalSession>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/terminals/${encodeURIComponent(terminalId)}`,
    {
      headers: { 'x-project-id': projectId },
      signal,
    },
  );
  return res.data;
}
