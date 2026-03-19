import axios from 'axios';

const TOKEN_STORAGE_KEY = 'auth_token';
const USER_STORAGE_KEY = 'auth_user';
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
    localStorage.removeItem(USER_STORAGE_KEY);
}

export function isAuthenticated() {
    const token = getAuthToken();
    if (!token) return false;
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now();
    } catch {
        clearAuthToken();
        return false;
    }
}

export function logout() {
    clearAuthToken();
}

export function getCurrentUser() {
    try {
        const raw = localStorage.getItem(USER_STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

export function getAuthErrorMessage(error, fallbackMessage = "L'authentification a échoué. Veuillez réessayer.") {
    if (axios.isAxiosError(error)) {
        if (error.code === 'ERR_NETWORK') {
            return 'Le serveur est momentanément indisponible. Veuillez réessayer dans quelques instants.';
        }
        if (error.code === 'ECONNABORTED') {
            return 'Le serveur met trop de temps à répondre. Veuillez réessayer.';
        }
        return error.response?.data?.message || error.response?.data?.detail || fallbackMessage;
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

        const user = payload?.data?.user || {};
        if (user.nom || user.email) {
            localStorage.setItem(USER_STORAGE_KEY, JSON.stringify({ nom: user.nom, email: user.email }));
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
