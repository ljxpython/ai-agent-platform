export type PreviewKind = 'text' | 'markdown' | 'image' | 'html-sandbox' | 'download';

export interface WorkspaceCapabilities {
  workspace: boolean;
  artifacts?: string[];
  terminal?: boolean;
}

export interface WorkspaceEntry {
  path: string;
  name: string;
  type: 'file' | 'directory';
  size_bytes: number | null;
  mtime: string;
  mime_type: string | null;
  preview_kind: PreviewKind | null;
  is_artifact: boolean;
}

export interface ArtifactRef {
  version: 1;
  artifact_id: string;
  path: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  kind: string;
  preview_kind: PreviewKind;
}

export interface WorkspacePage<T> {
  items: T[];
  next_cursor: string | null;
}

export interface TextPreview {
  path: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  preview_kind: 'text' | 'markdown';
  text: string;
  truncated: boolean;
}

export type TerminalBackend = 'local' | 'docker';
export type TerminalIsolation = 'host-development' | 'docker';
export type TerminalStatus = 'running' | 'exited';
export type TerminalExitReason =
  | null
  | 'shell_exit'
  | 'closed'
  | 'idle_expired'
  | 'lifetime_expired'
  | 'runtime_shutdown'
  | 'disabled';

export interface TerminalSession {
  terminal_id: string;
  backend: TerminalBackend;
  isolation: TerminalIsolation;
  status: TerminalStatus;
  exit_code: number | null;
  reason: TerminalExitReason;
  rows: number;
  cols: number;
  next_input_sequence: number;
  start_offset: number;
  end_offset: number;
}

export interface TerminalOutput extends TerminalSession {
  data_base64: string;
  offset: number;
  next_offset: number;
  truncated: boolean;
}

export interface TerminalInputAck {
  accepted_bytes: number;
  next_input_sequence: number;
}

export interface TerminalListResponse {
  items: TerminalSession[];
  instance_id: string;
}
