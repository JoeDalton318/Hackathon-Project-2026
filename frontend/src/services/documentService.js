import { getDocuments, getHealth, uploadDocuments } from './api';

export async function getHealthStatus() {
    return getHealth();
}

export async function processDocuments(files) {
    return uploadDocuments(files);
}

export { getDocuments, uploadDocuments };