import axios from 'axios';

const TOKEN_STORAGE_KEY = 'auth_token';
const AUTH_BASE_URL = process.env.REACT_APP_API_BASE_URL || process.env.REACT_APP_API_URL || 'http://localhost:8000';

function extractToken(payload) {
    return (
        payload?.access_token ||
        payload?.token ||
        payload?.data?.access_token ||
        payload?.data?.token ||
        ''
    );
}

export function saveAuthToken(token) {
    if (typeof token === 'string' && token.trim().length > 0) {
        localStorage.setItem(TOKEN_STORAGE_KEY, token);
    }
}

export function getAuthToken() {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || '';
}

export function clearAuthToken() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function isAuthenticated() {
    return Boolean(getAuthToken());
}

export function getAuthErrorMessage(error, fallbackMessage = 'Authentication failed.') {
    if (axios.isAxiosError(error)) {
        return (
            error.response?.data?.message ||
            error.response?.data?.detail ||
            error.message ||
            fallbackMessage
        );
    }

    if (error instanceof Error) {
        return error.message || fallbackMessage;
    }

    return fallbackMessage;
}

export async function login(email, password) {
    try {
        const response = await axios.post(`${AUTH_BASE_URL}/auth/login`, { email, password }, {
            headers: {
                'Content-Type': 'application/json',
            },
        });
        const payload = response?.data ?? {};
        console.log('[AUTH] POST /auth/login success');

        const token = extractToken(payload);
        if (token) {
            saveAuthToken(token);
        }

        return {
            ...payload,
            token,
        };
    } catch (error) {
        console.error('[AUTH] POST /auth/login failed', error);
        throw error;
    }
}

export async function register(name, email, password) {
    try {
        const response = await axios.post(`${AUTH_BASE_URL}/auth/register`, { nom: name, email, password }, {
            headers: {
                'Content-Type': 'application/json',
            },
        });
        const payload = response?.data ?? {};
        console.log('[AUTH] POST /auth/register success');

        const token = extractToken(payload);

        return {
            ...payload,
            token,
        };
    } catch (error) {
        console.error('[AUTH] POST /auth/register failed', error);
        throw error;
    }
}
