import { create } from 'zustand';
import { User } from '@/types';
import { apiClient } from '@/api/client';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
  clearError: () => void;
  restoreSession: () => Promise<void>;
}

const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const tokens = await apiClient.login(email, password);
      // Fetch profile separately — login endpoint only returns tokens
      const user = await apiClient.getMe();
      set({
        user,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err: any) {
      let errorMsg = 'Login failed';
      const detail = err.response?.data?.detail;
      
      if (typeof detail === 'string') {
        errorMsg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        // Pydantic validation error format
        errorMsg = detail.map((e: any) => e.msg || e.message || 'Validation error').join(', ');
      } else if (err.response?.data?.error) {
        errorMsg = err.response.data.error;
      }
      
      set({ error: errorMsg, isLoading: false });
      throw err;
    }
  },

  register: async (email: string, password: string, fullName?: string) => {
    set({ isLoading: true, error: null });
    try {
      const tokens = await apiClient.register(email, password, fullName);
      const user = await apiClient.getMe();
      set({
        user,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err: any) {
      let errorMsg = 'Registration failed';
      const detail = err.response?.data?.detail;
      
      if (typeof detail === 'string') {
        errorMsg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        // Pydantic validation error format
        errorMsg = detail.map((e: any) => e.msg || e.message || 'Validation error').join(', ');
      } else if (err.response?.data?.error) {
        errorMsg = err.response.data.error;
      }
      
      set({ error: errorMsg, isLoading: false });
      throw err;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    try {
      const { refreshToken } = get();
      if (refreshToken) {
        await apiClient.logout(refreshToken);
      }
    } finally {
      set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false, isLoading: false });
      apiClient.clearTokens();
    }
  },

  setUser: (user: User | null) => set({ user, isAuthenticated: !!user }),

  clearError: () => set({ error: null }),

  restoreSession: async () => {
    const stored = localStorage.getItem('auth_tokens');
    if (!stored) return;
    try {
      const { access_token, refresh_token } = JSON.parse(stored);
      if (!access_token) return;
      apiClient.setAccessToken(access_token);
      const user = await apiClient.getMe();
      set({ user, accessToken: access_token, refreshToken: refresh_token, isAuthenticated: true });
    } catch {
      // Token expired or invalid — clear and let user log in again
      apiClient.clearTokens();
      set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
    }
  },
}));

export default useAuthStore;
