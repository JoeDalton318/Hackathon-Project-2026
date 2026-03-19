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

export function getApiErrorMessage(error, fallbackMessage = 'Une erreur inattendue s\'est produite. Veuillez réessayer.') {
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

export default apiClient;