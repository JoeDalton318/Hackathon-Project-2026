import apiClient, { isApiConfigured } from './apiClient';

function assertApiConfigured() {
    if (!isApiConfigured) {
        throw new Error("L'application n'est pas correctement configurée. Veuillez contacter l'administrateur.");
    }
}

function unwrapResponse(response) {
    return response?.data?.data || response?.data || [];
}

const DECISION_MAP = {
    'valide': 'validated',
    'validé': 'validated',
    'accepté': 'validated',
    'accepte': 'validated',
    'ok': 'validated',
    'invalide': 'inconsistent',
    'rejeté': 'inconsistent',
    'rejete': 'inconsistent',
    'ko': 'inconsistent',
    'a_verifier': 'review',
    'a_vérifier': 'review',
    'en_attente': 'review',
    'review': 'review',
    'validated': 'validated',
    'inconsistent': 'inconsistent',
};

function mapDocumentToFrontend(doc) {
    const extracted = doc.extracted_data || {};
    const decisionRaw = (doc.decision || '').toLowerCase().trim();
    const validationStatus = DECISION_MAP[decisionRaw] || (doc.status === 'done' ? 'validated' : 'review');

    return {
        id: doc.document_id,
        filename: doc.original_filename,
        documentType: doc.document_type || 'inconnu',
        type: 'pdf',
        supplier: extracted.fournisseur || extracted.emetteur || extracted.nom_fournisseur || '',
        siren: extracted.siren || '',
        siret: extracted.siret || '',
        date: extracted.date || extracted.date_emission || '',
        extractedAmount: parseFloat(extracted.montant_ttc || extracted.montant || extracted.total) || 0,
        currency: extracted.devise || extracted.currency || 'EUR',
        status: doc.status,
        validationStatus,
        inconsistencies: doc.anomalies || [],
        uploadedAt: doc.created_at,
    };
}

export async function uploadDocuments(files) {
    assertApiConfigured();
    const formData = new FormData();
    files.forEach((file) => {
        formData.append('files', file);
    });

    const response = await apiClient.post('/documents/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return unwrapResponse(response);
}

export async function getDocuments() {
    assertApiConfigured();
    const response = await apiClient.get('/documents/');
    const data = response?.data?.data;
    const items = Array.isArray(data?.items) ? data.items : [];
    return items.map(mapDocumentToFrontend);
}

export async function getSuppliers() {
    assertApiConfigured();
    const response = await apiClient.get('/suppliers');
    return unwrapResponse(response);
}