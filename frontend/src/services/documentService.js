import apiClient, { isApiConfigured } from './apiClient';

function assertApiConfigured() {
    if (!isApiConfigured) {
        throw new Error('API not configured. Set REACT_APP_API_BASE_URL to enable backend requests.');
    }
}

function unwrapResponse(response) {
    return response?.data?.data || response?.data || [];
}

export async function uploadDocuments(files) {
    assertApiConfigured();
    const formData = new FormData();
    files.forEach((file) => {
        formData.append('files', file);
    });

    const response = await apiClient.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return unwrapResponse(response);
}

export async function processDocuments(payload = {}) {
    assertApiConfigured();
    const response = await apiClient.post('/process', payload);
    return unwrapResponse(response);
}

export async function getDocuments() {
    assertApiConfigured();
    const response = await apiClient.get('/documents');
    return unwrapResponse(response);
}

export async function getSuppliers() {
    assertApiConfigured();
    const response = await apiClient.get('/suppliers');
    return unwrapResponse(response);
}