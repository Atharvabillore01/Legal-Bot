// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
  last_login: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ─── Documents ────────────────────────────────────────────────────────────────

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  chunk_count: number;
  jurisdiction: string | null;
  authority_level: string;
  error_message: string | null;
  uploaded_at: string;
  processed_at: string | null;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
}

export interface IngestResponse {
  document_id: string;
  status: string;
  message: string;
  filename: string;
}

// ─── Query ────────────────────────────────────────────────────────────────────

export interface Citation {
  chunk_id: string;
  source_doc: string;
  page_number: number | null;
  text_excerpt: string;
  jurisdiction: string | null;
  section: string | null;
  character_offset_start: number;
  character_offset_end: number;
}

export interface SourceChunk {
  chunk_id: string;
  doc_name: string;
  page_number: number | null;
  section: string | null;
  jurisdiction: string | null;
  text: string;
  relevance_score: number;
  rank: number;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  source_chunks: SourceChunk[];
  confidence_score: number;
  confidence_level: 'LOW' | 'MEDIUM' | 'HIGH';
  query: string;
  search_time_ms: number;
  llm_time_ms: number;
  total_time_ms: number;
  model: string;
  created_at: string;
  has_contradictions: boolean;
}

// ─── Audit Log ────────────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, any> | null;
  status: string;
  latency_ms: number | null;
  created_at: string;
}

export interface AuditLogListResponse {
  logs: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Errors ───────────────────────────────────────────────────────────────────

export interface ApiError {
  error: string;
  detail?: string;
  request_id?: string;
}
