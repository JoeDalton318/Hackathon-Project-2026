import axios from 'axios';
import { clearAuthToken, getAuthToken } from './auth';

export const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: apiBaseUrl,
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use(
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

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error?.response?.status === 401) {
            clearAuthToken();
        }
        return Promise.reject(error);
    }
);

export function getApiErrorMessage(error, fallbackMessage = 'An unexpected API error occurred.') {
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

export async function getHealth() {
    try {
        const response = await api.get('/health');
        const data = response?.data ?? {};
        console.log('[API] GET /health', data);
        return data;
    } catch (error) {
        console.error('[API] GET /health failed', error);
        throw error;
    }
}

export async function getDocuments() {
    try {
        const response = await api.get('/documents');
        const payload = response?.data ?? {};
        const documents = Array.isArray(payload?.data) ? payload.data : [];
        console.log('[API] GET /documents payload', payload);
        console.log('[API] GET /documents extracted data', documents);
        return {
            data: documents,
        };
    } catch (error) {
        console.error('[API] GET /documents failed', error);
        throw error;
    }
}

export async function uploadDocuments(files) {
    const formData = new FormData();
    files.forEach((file) => {
        formData.append('files', file);
    });

    try {
        const response = await api.post('/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        const payload = response?.data ?? {};
        const uploadedFiles = Array.isArray(payload?.data) ? payload.data : [];
        const message = typeof payload?.message === 'string' ? payload.message : '';
        console.log('[API] POST /upload payload', payload);
        console.log('[API] POST /upload extracted data', uploadedFiles);

        return {
            data: uploadedFiles,
            message,
        };
    } catch (error) {
        console.error('[API] POST /upload failed', error);
        throw error;
    }
}

export default api;
