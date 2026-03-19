import axios from 'axios';

function readViteApiBaseUrl() {
    let value;
    try {
        value = import.meta.env.VITE_API_BASE_URL;
    } catch {
        value = undefined;
    }
    if (typeof value === 'string' && value.trim().length > 0) {
        return value.trim();
    }

    const fallback = process.env.VITE_API_BASE_URL || process.env.REACT_APP_API_BASE_URL;
    return typeof fallback === 'string' ? fallback.trim() : '';
}

const configuredBaseUrl = readViteApiBaseUrl();
export const isApiConfigured = typeof configuredBaseUrl === 'string' && configuredBaseUrl.trim().length > 0;
export const apiBaseUrl = configuredBaseUrl;

const apiClient = axios.create({
    baseURL: configuredBaseUrl || '',
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

export function getApiErrorMessage(error, fallbackMessage = 'An unexpected error occurred.') {
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

export default apiClient;