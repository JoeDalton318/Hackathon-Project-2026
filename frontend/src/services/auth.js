import axios from 'axios';

const TOKEN_STORAGE_KEY = 'auth_token';

function normalizeRootUrl(value) {
    const trimmed = typeof value === 'string' ? value.trim() : '';
    if (!trimmed) {
        return 'http://localhost:8000';
    }

    return trimmed.replace(/\/+$/, '');
}

const AUTH_ROOT_URL = normalizeRootUrl(process.env.REACT_APP_API_BASE_URL || process.env.REACT_APP_API_URL);
const AUTH_API_BASE_URL = AUTH_ROOT_URL.endsWith('/api') ? AUTH_ROOT_URL : `${AUTH_ROOT_URL}/api`;

function toReadableErrorDetail(detail) {
    if (typeof detail === 'string') {
        return detail;
    }

    if (Array.isArray(detail)) {
        return detail
            .map((entry) => {
                if (typeof entry === 'string') {
                    return entry;
                }

                if (entry && typeof entry === 'object') {
                    const location = Array.isArray(entry.loc) ? entry.loc.join('.') : '';
                    const message = typeof entry.msg === 'string' ? entry.msg : 'Invalid value';
                    return location ? `${location}: ${message}` : message;
                }

                return 'Invalid request payload';
            })
            .join(' | ');
    }

    if (detail && typeof detail === 'object') {
        return detail.message || JSON.stringify(detail);
    }

    return '';
}

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
        const readableDetail = toReadableErrorDetail(error.response?.data?.detail);
        return (
            error.response?.data?.message ||
            readableDetail ||
            error.response?.data?.error ||
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
        const response = await axios.post(`${AUTH_API_BASE_URL}/auth/login`, { email, password }, {
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
        const response = await axios.post(`${AUTH_API_BASE_URL}/auth/register`, { nom: name, name, email, password }, {
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
