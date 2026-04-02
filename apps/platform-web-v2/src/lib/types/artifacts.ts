export type ArtifactStatus =
  | "pending"
  | "ready"
  | "failed"
  | "deleted"
  | "expired";

export type ArtifactType =
  | "report"
  | "image"
  | "dataset"
  | "archive"
  | "document"
  | "other";

export interface ArtifactRecord {
  id: string;
  project_id: string;
  thread_id: string;
  assistant_id?: string | null;
  graph_id?: string | null;
  producer: string;
  artifact_name: string;
  artifact_type: ArtifactType;
  mime_type: string;
  storage_type: string;
  size_bytes?: number | null;
  checksum?: string | null;
  status: ArtifactStatus;
  summary?: string | null;
  preview_text?: string | null;
  metadata_json?: Record<string, unknown>;
  download_url: string;
  preview_url?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
}

export interface ArtifactCandidateBlock {
  type: "artifact_candidate";
  title?: string;
  description?: string;
  artifact_name: string;
  artifact_type?: ArtifactType;
  mime_type?: string;
  relative_path: string;
  source_kind?: "local_file" | "state_file" | "generated_text";
  status?: ArtifactStatus;
  preview_text?: string | null;
}

export interface ArtifactRefBlock {
  type: "artifact_ref";
  artifact_id: string;
  title: string;
  description?: string;
  mime_type?: string;
  status?: ArtifactStatus;
}
