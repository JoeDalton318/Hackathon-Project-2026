import axios from 'axios';
import { clearAuthToken, getAuthToken } from './auth';

function readApiBaseUrl() {
    const value = process.env.REACT_APP_API_BASE_URL || process.env.REACT_APP_API_URL || 'http://localhost:8000';
    return typeof value === 'string' ? value.trim() : 'http://localhost:8000';
}

const configuredBaseUrl = readApiBaseUrl();
export const isApiConfigured = Boolean(configuredBaseUrl);
export const apiBaseUrl = configuredBaseUrl;

const apiClient = axios.create({
    baseURL: configuredBaseUrl,
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.request.use(
    (config) => {
        const token = getAuthToken();
        if (token) {
            config.headers = {
                ...config.headers,
                Authorization: `Bearer ${token}`,
            };
        }
        return config;
    },
    (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error?.response?.status === 401) {
            clearAuthToken();
        }
        return Promise.reject(error);
    }
);

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