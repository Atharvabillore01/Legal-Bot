import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  TokenResponse, AccessTokenResponse, User,
  QueryResponse, AuditLogListResponse, DocumentListResponse, IngestResponse,
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_TIMEOUT = Number(import.meta.env.VITE_API_TIMEOUT || 60000);

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: API_TIMEOUT,
      headers: { 'Content-Type': 'application/json' },
    });

    // Attach token to every request
    this.client.interceptors.request.use((config) => {
      if (this.accessToken) {
        config.headers.Authorization = `Bearer ${this.accessToken}`;
      }
      return config;
    });

    // Auto-redirect on 401
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          this.clearTokens();
          window.location.href = '/login';
        }
        return Promise.reject(error);
      },
    );

    // Restore token from storage on init
    const stored = localStorage.getItem('auth_tokens');
    if (stored) {
      try {
        const { access_token } = JSON.parse(stored);
        if (access_token) this.accessToken = access_token;
      } catch {
        // ignore malformed storage
      }
    }
  }

  setAccessToken(token: string) {
    this.accessToken = token;
  }

  clearTokens() {
    this.accessToken = null;
    localStorage.removeItem('auth_tokens');
  }

  // ─── Auth ──────────────────────────────────────────────────────────────────

  async register(email: string, password: string, fullName?: string): Promise<TokenResponse> {
    const { data } = await this.client.post<TokenResponse>('/auth/register', {
      email,
      password,
      full_name: fullName,
    });
    this._storeTokens(data.access_token, data.refresh_token);
    return data;
  }

  async login(email: string, password: string): Promise<TokenResponse> {
    const { data } = await this.client.post<TokenResponse>('/auth/login', { email, password });
    this._storeTokens(data.access_token, data.refresh_token);
    return data;
  }

  async refreshToken(refreshToken: string): Promise<AccessTokenResponse> {
    const { data } = await this.client.post<AccessTokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    this.accessToken = data.access_token;
    // Update stored access token, keep refresh token
    const stored = localStorage.getItem('auth_tokens');
    if (stored) {
      const parsed = JSON.parse(stored);
      localStorage.setItem('auth_tokens', JSON.stringify({
        ...parsed,
        access_token: data.access_token,
      }));
    }
    return data;
  }

  async logout(refreshToken: string): Promise<void> {
    try {
      await this.client.post('/auth/logout', { refresh_token: refreshToken });
    } finally {
      this.clearTokens();
    }
  }

  async getMe(): Promise<User> {
    const { data } = await this.client.get<User>('/auth/me');
    return data;
  }

  // ─── Documents ─────────────────────────────────────────────────────────────

  async uploadDocument(
    file: File,
    jurisdiction?: string,
    authorityLevel: string = 'reference',
  ): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (jurisdiction) formData.append('jurisdiction', jurisdiction);
    formData.append('authority_level', authorityLevel);

    const { data } = await this.client.post<IngestResponse>('/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  }

  async listDocuments(page = 1, pageSize = 20): Promise<DocumentListResponse> {
    const { data } = await this.client.get<DocumentListResponse>('/documents', {
      params: { page, page_size: pageSize },
    });
    return data;
  }

  async getDocument(docId: string): Promise<import('@/types').Document> {
    const { data } = await this.client.get(`/documents/${docId}`);
    return data;
  }

  async deleteDocument(docId: string): Promise<void> {
    await this.client.delete(`/documents/${docId}`);
  }

  // ─── Query ─────────────────────────────────────────────────────────────────

  async submitQuery(
    query: string,
    k = 7,
    jurisdiction?: string,
    docIds?: string[],
  ): Promise<QueryResponse> {
    const { data } = await this.client.post<QueryResponse>('/query', {
      query,
      k,
      jurisdiction: jurisdiction || undefined,
      doc_ids: docIds || undefined,
      detect_contradictions: true,
      rerank: true,
    });
    return data;
  }

  // ─── Audit Log ─────────────────────────────────────────────────────────────

  async getAuditLog(
    page = 1,
    pageSize = 50,
    action?: string,
  ): Promise<AuditLogListResponse> {
    const { data } = await this.client.get<AuditLogListResponse>('/audit-log', {
      params: { page, page_size: pageSize, action },
    });
    return data;
  }

  // ─── Health ────────────────────────────────────────────────────────────────

  async healthCheck(): Promise<{ status: string; version: string }> {
    const { data } = await this.client.get('/health');
    return data;
  }

  // ─── Private ───────────────────────────────────────────────────────────────

  private _storeTokens(accessToken: string, refreshToken: string) {
    this.accessToken = accessToken;
    localStorage.setItem('auth_tokens', JSON.stringify({ access_token: accessToken, refresh_token: refreshToken }));
  }
}

export const apiClient = new ApiClient();
