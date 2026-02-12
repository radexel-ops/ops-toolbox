/**
 * VibeOps Authentication Module
 *
 * Handles user authentication, token management, and session state.
 */

const AUTH_TOKEN_KEY = 'vibeops_access_token';
const REFRESH_TOKEN_KEY = 'vibeops_refresh_token';
const USER_KEY = 'vibeops_user';

class AuthManager {
    constructor() {
        this.user = null;
        this.loadStoredAuth();
    }

    /**
     * Load stored authentication from localStorage
     */
    loadStoredAuth() {
        const userJson = localStorage.getItem(USER_KEY);
        if (userJson) {
            try {
                this.user = JSON.parse(userJson);
            } catch (e) {
                this.clearAuth();
            }
        }
    }

    /**
     * Get access token
     */
    getAccessToken() {
        return localStorage.getItem(AUTH_TOKEN_KEY);
    }

    /**
     * Get refresh token
     */
    getRefreshToken() {
        return localStorage.getItem(REFRESH_TOKEN_KEY);
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!this.getAccessToken() && !!this.user;
    }

    /**
     * Get current user
     */
    getUser() {
        return this.user;
    }

    /**
     * Login with email and password
     */
    async login(email, password) {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const tokens = await response.json();

        // Store tokens
        localStorage.setItem(AUTH_TOKEN_KEY, tokens.access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);

        // Fetch user info
        await this.fetchCurrentUser();

        return this.user;
    }

    /**
     * Fetch current user info
     */
    async fetchCurrentUser() {
        const token = this.getAccessToken();
        if (!token) return null;

        const response = await fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`,
            },
        });

        if (!response.ok) {
            this.clearAuth();
            return null;
        }

        this.user = await response.json();
        localStorage.setItem(USER_KEY, JSON.stringify(this.user));

        return this.user;
    }

    /**
     * Refresh access token
     */
    async refreshTokens() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) return false;

        const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!response.ok) {
            this.clearAuth();
            return false;
        }

        const tokens = await response.json();
        localStorage.setItem(AUTH_TOKEN_KEY, tokens.access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);

        return true;
    }

    /**
     * Logout
     */
    async logout() {
        const refreshToken = this.getRefreshToken();

        if (refreshToken) {
            try {
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ refresh_token: refreshToken }),
                });
            } catch (e) {
                console.error('Logout request failed:', e);
            }
        }

        this.clearAuth();
    }

    /**
     * Clear stored authentication
     */
    clearAuth() {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        this.user = null;
    }

    /**
     * Make authenticated API request
     */
    async apiRequest(url, options = {}) {
        const token = this.getAccessToken();

        const headers = {
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(url, {
            ...options,
            headers,
        });

        // Handle token expiration
        if (response.status === 401) {
            const refreshed = await this.refreshTokens();
            if (refreshed) {
                // Retry with new token
                headers['Authorization'] = `Bearer ${this.getAccessToken()}`;
                return fetch(url, { ...options, headers });
            } else {
                // Redirect to login
                window.location.href = '/login.html';
            }
        }

        return response;
    }
}

// Global auth manager instance
const authManager = new AuthManager();
