import axios from 'axios';

const TOKEN_STORAGE_KEY = 'auth_token';

function normalizeRootUrl(value) {
    const trimmed = typeof value === 'string' ? value.trim() : '';
    if (!trimmed) {
        return 'http://localhost:8000';
    }

    return trimmed.replace(/\/+$/, '');
}

function normalizeApiBaseUrl(rootUrl) {
    return rootUrl.endsWith('/api') ? rootUrl : `${rootUrl}/api`;
}

const configuredRootUrl = normalizeRootUrl(process.env.REACT_APP_API_BASE_URL);

export const apiRootUrl = configuredRootUrl;
export const apiBaseUrl = normalizeApiBaseUrl(configuredRootUrl);
export const isApiConfigured = Boolean(apiBaseUrl);

const apiClient = axios.create({
    baseURL: apiBaseUrl,
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (token) {
        config.headers = {
            ...config.headers,
            Authorization: `Bearer ${token}`,
        };
    }

    return config;
});

apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error?.response?.status === 401) {
            localStorage.removeItem(TOKEN_STORAGE_KEY);
        }
        return Promise.reject(error);
    }
);

export function unwrapApiData(response) {
    if (response?.data && typeof response.data === 'object' && 'data' in response.data) {
        return response.data.data;
    }

    return response?.data;
}

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

export function getApiErrorMessage(error, fallbackMessage = 'An unexpected error occurred.') {
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

export default apiClient;