import axios from 'axios';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_TIMEOUT = Number(import.meta.env.VITE_API_TIMEOUT || 60000);
class ApiClient {
    constructor() {
        Object.defineProperty(this, "client", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "accessToken", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: null
        });
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
        this.client.interceptors.response.use((response) => response, (error) => {
            if (error.response?.status === 401) {
                this.clearTokens();
                window.location.href = '/login';
            }
            return Promise.reject(error);
        });
        // Restore token from storage on init
        const stored = localStorage.getItem('auth_tokens');
        if (stored) {
            try {
                const { access_token } = JSON.parse(stored);
                if (access_token)
                    this.accessToken = access_token;
            }
            catch {
                // ignore malformed storage
            }
        }
    }
    setAccessToken(token) {
        this.accessToken = token;
    }
    clearTokens() {
        this.accessToken = null;
        localStorage.removeItem('auth_tokens');
    }
    // ─── Auth ──────────────────────────────────────────────────────────────────
    async register(email, password, fullName) {
        const { data } = await this.client.post('/auth/register', {
            email,
            password,
            full_name: fullName,
        });
        this._storeTokens(data.access_token, data.refresh_token);
        return data;
    }
    async login(email, password) {
        const { data } = await this.client.post('/auth/login', { email, password });
        this._storeTokens(data.access_token, data.refresh_token);
        return data;
    }
    async refreshToken(refreshToken) {
        const { data } = await this.client.post('/auth/refresh', {
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
    async logout(refreshToken) {
        try {
            await this.client.post('/auth/logout', { refresh_token: refreshToken });
        }
        finally {
            this.clearTokens();
        }
    }
    async getMe() {
        const { data } = await this.client.get('/auth/me');
        return data;
    }
    // ─── Documents ─────────────────────────────────────────────────────────────
    async uploadDocument(file, jurisdiction, authorityLevel = 'reference') {
        const formData = new FormData();
        formData.append('file', file);
        if (jurisdiction)
            formData.append('jurisdiction', jurisdiction);
        formData.append('authority_level', authorityLevel);
        const { data } = await this.client.post('/ingest', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return data;
    }
    async listDocuments(page = 1, pageSize = 20) {
        const { data } = await this.client.get('/documents', {
            params: { page, page_size: pageSize },
        });
        return data;
    }
    async getDocument(docId) {
        const { data } = await this.client.get(`/documents/${docId}`);
        return data;
    }
    async deleteDocument(docId) {
        await this.client.delete(`/documents/${docId}`);
    }
    // ─── Query ─────────────────────────────────────────────────────────────────
    async submitQuery(query, k = 7, jurisdiction, docIds) {
        const { data } = await this.client.post('/query', {
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
    async getAuditLog(page = 1, pageSize = 50, action) {
        const { data } = await this.client.get('/audit-log', {
            params: { page, page_size: pageSize, action },
        });
        return data;
    }
    // ─── Health ────────────────────────────────────────────────────────────────
    async healthCheck() {
        const { data } = await this.client.get('/health');
        return data;
    }
    // ─── Private ───────────────────────────────────────────────────────────────
    _storeTokens(accessToken, refreshToken) {
        this.accessToken = accessToken;
        localStorage.setItem('auth_tokens', JSON.stringify({ access_token: accessToken, refresh_token: refreshToken }));
    }
}
export const apiClient = new ApiClient();
