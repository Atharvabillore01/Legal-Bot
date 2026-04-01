import { create } from 'zustand';
import { apiClient } from '@/api/client';
const useAuthStore = create((set, get) => ({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    login: async (email, password) => {
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
        }
        catch (err) {
            set({
                error: err.response?.data?.detail || err.response?.data?.error || 'Login failed',
                isLoading: false,
            });
            throw err;
        }
    },
    register: async (email, password, fullName) => {
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
        }
        catch (err) {
            set({
                error: err.response?.data?.detail || err.response?.data?.error || 'Registration failed',
                isLoading: false,
            });
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
        }
        finally {
            set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false, isLoading: false });
            apiClient.clearTokens();
        }
    },
    setUser: (user) => set({ user, isAuthenticated: !!user }),
    clearError: () => set({ error: null }),
    restoreSession: async () => {
        const stored = localStorage.getItem('auth_tokens');
        if (!stored)
            return;
        try {
            const { access_token, refresh_token } = JSON.parse(stored);
            if (!access_token)
                return;
            apiClient.setAccessToken(access_token);
            const user = await apiClient.getMe();
            set({ user, accessToken: access_token, refreshToken: refresh_token, isAuthenticated: true });
        }
        catch {
            // Token expired or invalid — clear and let user log in again
            apiClient.clearTokens();
            set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
        }
    },
}));
export default useAuthStore;
