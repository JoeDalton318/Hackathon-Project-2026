import axios from 'axios';
import { clearAuthToken, getAuthToken } from './auth';

const configuredBaseUrl = process.env.REACT_APP_API_BASE_URL;
export const isApiConfigured = typeof configuredBaseUrl === 'string' && configuredBaseUrl.trim().length > 0;

const apiClient = axios.create({
    baseURL: configuredBaseUrl || '',
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.request.use((config) => {
    const token = getAuthToken();
    if (token) {
        config.headers = { ...config.headers, Authorization: `Bearer ${token}` };
    }
    return config;
});

apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error?.response?.status === 401) {
            clearAuthToken();
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
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