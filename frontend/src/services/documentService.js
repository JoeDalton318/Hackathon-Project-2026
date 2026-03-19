import apiClient, { isApiConfigured, unwrapApiData } from './apiClient';

function assertApiConfigured() {
    if (!isApiConfigured) {
        throw new Error('API not configured. Set REACT_APP_API_BASE_URL to enable backend requests.');
    }
}

function toNumber(value, fallback = 0) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }

    if (typeof value === 'string') {
        const normalized = Number(value.replace(',', '.').replace(/\s+/g, ''));
        if (Number.isFinite(normalized)) {
            return normalized;
        }
    }

    return fallback;
}

function pickByPath(source, path) {
    if (!source || typeof source !== 'object') {
        return undefined;
    }

    const parts = path.split('.');
    let current = source;

    for (const part of parts) {
        if (current == null || typeof current !== 'object' || !(part in current)) {
            return undefined;
        }
        current = current[part];
    }

    return current;
}

function firstDefinedByPaths(source, paths) {
    for (const path of paths) {
        const value = pickByPath(source, path);
        if (value !== undefined && value !== null && value !== '') {
            return value;
        }
    }

    return undefined;
}

function firstDefinedEntryByPaths(source, paths) {
    for (const path of paths) {
        const value = pickByPath(source, path);
        if (value !== undefined && value !== null && value !== '') {
            return { path, value };
        }
    }

    return { path: 'unmapped', value: undefined };
}

function resolveFirstValue(...candidates) {
    for (const value of candidates) {
        if (typeof value === 'string' && value.trim().length > 0) {
            return value.trim();
        }
    }

    return '';
}

function computeValidationStatus(record, anomaliesCount) {
    const decision = (record?.decision || '').toLowerCase();
    const status = (record?.status || '').toLowerCase();

    if (decision === 'blocked') {
        return 'inconsistent';
    }

    if (decision === 'review') {
        return 'review';
    }

    if (decision === 'approved') {
        return 'validated';
    }

    if (anomaliesCount > 0 || status === 'error') {
        return 'inconsistent';
    }

    if (status === 'done' || status === 'extraction_done' || status === 'ocr_done') {
        return 'validated';
    }

    return 'review';
}

export function normalizeDocument(record) {
    const extracted = record?.extracted_data || {};
    const fournisseur = extracted?.fournisseur || {};
    const titulaireCompte = extracted?.titulaire_compte || {};

    const siret = resolveFirstValue(
        extracted.siret,
        extracted.siret_emetteur,
        fournisseur.siret,
        titulaireCompte.siret,
        titulaireCompte.siret_ou_siren,
        extracted.siret_siege,
        firstDefinedByPaths(extracted, [
            'fields.siret',
            'fields.siret_ou_siren',
            'facture.emetteur.siret.value',
            'devis.emetteur.siret.value',
            'attestation_siret.siret.value',
            'attestation_urssaf.siret.value',
            'rib.titulaire.siret.value',
        ])
    );

    const supplier = resolveFirstValue(
        extracted.supplier_name,
        extracted.raison_sociale,
        fournisseur.raison_sociale,
        titulaireCompte.raison_sociale,
        firstDefinedByPaths(extracted, [
            'fields.supplier_name',
            'fields.denomination',
            'facture.emetteur.nom.value',
            'devis.emetteur.nom.value',
            'attestation_siret.denomination.value',
            'attestation_urssaf.denomination.value',
            'rib.titulaire.nom.value',
        ]),
        siret ? `Supplier ${siret}` : ''
    ) || 'Unknown supplier';

    const anomalies = Array.isArray(record?.anomalies) ? record.anomalies : [];
    const inconsistencies = anomalies.map((anomaly) => {
        if (typeof anomaly === 'string') {
            return anomaly;
        }

        if (anomaly && typeof anomaly === 'object') {
            return anomaly.description || anomaly.message || anomaly.type || 'Anomaly detected';
        }

        return 'Anomaly detected';
    });

    const amountEntry = firstDefinedEntryByPaths(extracted, [
        'montant_ttc',
        'amount',
        'total_ttc',
        'total_amount',
        'amount_ttc',
        'fields.amount_ttc',
        'fields.montant_ttc',
        'facture.montant_ttc.value',
        'devis.montant_ttc.value',
        'facture.montant_ht.value',
        'devis.montant_ht.value',
    ]);

    const extractedAmount = toNumber(amountEntry.value, 0);

    const invoiceNumber = resolveFirstValue(
        extracted.numero_facture,
        extracted.invoice_number,
        firstDefinedByPaths(extracted, [
            'fields.numero_facture',
            'facture.numero_facture.value',
            'devis.numero_devis.value',
        ])
    );

    const extractedDate = resolveFirstValue(
        extracted.date_facture,
        extracted.date,
        firstDefinedByPaths(extracted, [
            'fields.date_facture',
            'fields.invoice_date',
            'facture.date_emission.value',
            'devis.date_emission.value',
        ])
    );

    const extractedCurrency = resolveFirstValue(
        extracted.currency,
        firstDefinedByPaths(extracted, [
            'fields.devise',
            'facture.devise.value',
            'devis.devise.value',
        ]),
        'EUR'
    );

    const normalizedStatus = computeValidationStatus(record, anomalies.length);

    return {
        id: record.document_id,
        document_id: record.document_id,
        filename: record.original_filename,
        originalFilename: record.original_filename,
        documentType: record.document_type || 'inconnu',
        type: record.mime_type || 'unknown',
        supplier,
        invoiceNumber,
        siren: resolveFirstValue(extracted.siren, siret.slice(0, 9)),
        siret,
        date: extractedDate,
        amount: extractedAmount,
        extractedAmount,
        amountSource: amountEntry.path,
        currency: extractedCurrency,
        status: (record.status || 'pending').toLowerCase(),
        validationStatus: normalizedStatus,
        inconsistencies,
        uploadedAt: record.created_at,
    };
}

function normalizeDocumentsPayload(payload) {
    if (Array.isArray(payload)) {
        return payload.map(normalizeDocument);
    }

    if (payload && Array.isArray(payload.items)) {
        return payload.items.map(normalizeDocument);
    }

    return [];
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

    const data = unwrapApiData(response);
    return Array.isArray(data?.documents) ? data.documents : [];
}

export async function processDocument(documentId) {
    assertApiConfigured();
    if (!documentId) {
        return null;
    }

    const response = await apiClient.post(`/documents/${documentId}/process`);
    return unwrapApiData(response);
}

export async function processDocuments(payload = {}) {
    assertApiConfigured();

    const documentIds = Array.isArray(payload.documentIds)
        ? payload.documentIds.filter(Boolean)
        : [];

    if (documentIds.length === 0) {
        return [];
    }

    return Promise.all(documentIds.map((documentId) => processDocument(documentId)));
}

export async function getDocuments() {
    assertApiConfigured();
    const response = await apiClient.get('/documents');
    const payload = unwrapApiData(response);
    return normalizeDocumentsPayload(payload);
}

export async function getSuppliers() {
    const documents = await getDocuments();
    const suppliersByKey = new Map();

    documents.forEach((document) => {
        const key = `${document.supplier || 'unknown'}::${document.siret || ''}`;
        const existing = suppliersByKey.get(key);

        if (!existing) {
            suppliersByKey.set(key, {
                id: key,
                name: document.supplier || 'Unknown supplier',
                siren: document.siren || 'Not available',
                category: 'Uncategorized',
                country: 'Unknown',
                contactEmail: '',
                contactPhone: '',
                currency: document.currency || 'EUR',
                totalAmount: document.extractedAmount || 0,
                documentCount: 1,
                lastActivity: (document.uploadedAt || '').slice(0, 10),
                status: 'active',
                reliability: document.validationStatus === 'inconsistent' ? 60 : 95,
            });
            return;
        }

        existing.documentCount += 1;
        existing.totalAmount += document.extractedAmount || 0;

        const existingDate = new Date(existing.lastActivity || 0).getTime();
        const incomingDate = new Date(document.uploadedAt || 0).getTime();
        if (incomingDate > existingDate) {
            existing.lastActivity = (document.uploadedAt || '').slice(0, 10);
        }

        if (document.validationStatus === 'inconsistent') {
            existing.reliability = Math.max(40, existing.reliability - 10);
        }
    });

    return Array.from(suppliersByKey.values());
}