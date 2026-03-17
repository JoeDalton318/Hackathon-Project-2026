import axios from 'axios';

const configuredBaseUrl = process.env.REACT_APP_API_BASE_URL;
export const isApiConfigured = typeof configuredBaseUrl === 'string' && configuredBaseUrl.trim().length > 0;

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