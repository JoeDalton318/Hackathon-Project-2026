import { useState, useCallback, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import {
    Upload,
    FileText,
    FileImage,
    File,
    X,
    CheckCircle,
    Loader2,
    Play,
    AlertCircle,
    Sparkles,
    Activity,
    FolderOpen,
    ShieldCheck,
} from 'lucide-react';
import { getApiErrorMessage, getDocuments, uploadDocuments } from '../services/api';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Card from '../components/ui/Card';

const ACCEPTED_TYPES = {
    'application/pdf': ['.pdf'],
    'image/png': ['.png'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/tiff': ['.tiff', '.tif'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
};

const DOCUMENT_TYPES = [
    { value: 'invoice', label: 'Invoice' },
    { value: 'quote', label: 'Quote' },
    { value: 'certificate', label: 'Certificate' },
];

const INITIAL_FORM_STATE = {
    documentType: 'invoice',
    supplierName: '',
    invoiceNumber: '',
    invoiceDate: '',
    amount: '',
    currency: 'EUR',
    quoteReference: '',
    validUntil: '',
    certificateType: '',
    issuer: '',
    hasExpiry: false,
    expiryDate: '',
};

function getFileIcon(file) {
    if (file.type.startsWith('image/')) return FileImage;
    if (file.type === 'application/pdf') return FileText;
    return File;
}

function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileCard({ file, onRemove }) {
    const Icon = getFileIcon(file);
    return (
        <Card className="group flex items-center gap-4 rounded-xl px-4 py-3 shadow-soft">
            {file.preview ? (
                <img
                    src={file.preview}
                    alt={file.name}
                    className="w-12 h-12 rounded-lg object-cover flex-shrink-0 border border-gray-100"
                />
            ) : (
                <div className="w-12 h-12 rounded-lg bg-sky-50 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-5 h-5 text-sky-500" />
                </div>
            )}
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{file.name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{formatSize(file.size)}</p>
            </div>
            <div className="flex items-center gap-2">
                <Badge variant="success">Ready</Badge>
                <button
                    onClick={() => onRemove(file.name)}
                    className="ml-1 p-1 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>
        </Card>
    );
}

function SummaryCard({ icon: Icon, label, value, tone }) {
    return (
        <Card className="rounded-2xl p-4 shadow-soft">
            <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-2xl ${tone}`}>
                <Icon className="h-4 w-4" />
            </div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">{label}</p>
            <p className="mt-1 text-lg font-bold text-gray-900">{value}</p>
        </Card>
    );
}

export default function UploadPage() {
    const filesRef = useRef([]);
    const [files, setFiles] = useState([]);
    const [processing, setProcessing] = useState(false);
    const [uploadedFiles, setUploadedFiles] = useState([]);
    const [statusMessage, setStatusMessage] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const [formState, setFormState] = useState(INITIAL_FORM_STATE);
    const [formErrors, setFormErrors] = useState({});
    useEffect(() => {
        filesRef.current = files;
    }, [files]);

    useEffect(() => {
        return () => {
            filesRef.current.forEach((file) => {
                if (file.preview) {
                    URL.revokeObjectURL(file.preview);
                }
            });
        };
    }, []);

    const onDrop = useCallback((acceptedFiles) => {
        setErrorMessage('');
        setStatusMessage('');
        const withPreviews = acceptedFiles.map((f) =>
            Object.assign(f, {
                preview: f.type.startsWith('image/') ? URL.createObjectURL(f) : null,
            })
        );
        setFiles((prev) => {
            const existing = new Set(prev.map((f) => f.name));
            return [...prev, ...withPreviews.filter((f) => !existing.has(f.name))];
        });
    }, []);

    const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
        onDrop,
        accept: ACCEPTED_TYPES,
        multiple: true,
    });

    const removeFile = (name) => {
        setFiles((prev) => {
            const removed = prev.find((f) => f.name === name);
            if (removed?.preview) URL.revokeObjectURL(removed.preview);
            return prev.filter((f) => f.name !== name);
        });
    };

    const clearAll = () => {
        files.forEach((f) => f.preview && URL.revokeObjectURL(f.preview));
        setFiles([]);
        setUploadedFiles([]);
        setErrorMessage('');
        setStatusMessage('');
    };

    const updateFormField = (key, value) => {
        setFormState((prev) => ({ ...prev, [key]: value }));
        setFormErrors((prev) => ({ ...prev, [key]: '' }));
    };

    const validateForm = () => {
        const errors = {};
        if (!formState.supplierName.trim()) {
            errors.supplierName = 'Supplier name is required.';
        }

        if (formState.documentType === 'invoice') {
            if (!formState.invoiceNumber.trim()) errors.invoiceNumber = 'Invoice number is required.';
            if (!formState.invoiceDate) errors.invoiceDate = 'Invoice date is required.';
            if (!formState.amount || Number(formState.amount) <= 0) errors.amount = 'Enter a valid amount.';
        }

        if (formState.documentType === 'quote') {
            if (!formState.quoteReference.trim()) errors.quoteReference = 'Quote reference is required.';
            if (!formState.validUntil) errors.validUntil = 'Validity date is required.';
            if (!formState.amount || Number(formState.amount) <= 0) errors.amount = 'Enter a valid quote amount.';
        }

        if (formState.documentType === 'certificate') {
            if (!formState.certificateType.trim()) errors.certificateType = 'Certificate type is required.';
            if (!formState.issuer.trim()) errors.issuer = 'Issuer is required.';
            if (formState.hasExpiry && !formState.expiryDate) errors.expiryDate = 'Expiry date is required.';
        }

        setFormErrors(errors);
        return Object.keys(errors).length === 0;
    };

    const handleProcess = async () => {
        if (!files.length || processing) return;

        if (!validateForm()) {
            setErrorMessage('Please complete required metadata fields before processing.');
            return;
        }

        setProcessing(true);
        setErrorMessage('');

        try {
            setStatusMessage('Uploading documents...');
            const uploadResponse = await uploadDocuments(files);
            console.log('[UploadPage] upload response', uploadResponse);
            const uploaded = Array.isArray(uploadResponse?.data) ? uploadResponse.data : [];
            const successMessage = uploadResponse?.message || 'Upload completed successfully.';
            setUploadedFiles(uploaded);
            setStatusMessage(successMessage);

            // Refresh backend documents after upload to keep downstream views in sync.
            const refreshedDocuments = await getDocuments();
            console.log('[UploadPage] refreshed /documents response', refreshedDocuments);
        } catch (error) {
            console.error('[UploadPage] upload failed', error);
            setErrorMessage(getApiErrorMessage(error, 'Unable to upload documents to backend.'));
            setStatusMessage('');
            setUploadedFiles([]);
        } finally {
            setProcessing(false);
        }
    };

    return (
        <div className="saas-fade-in mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
            <div className="mb-8 grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_320px]">
                <div className="saas-rise rounded-[28px] border border-sky-100 bg-gradient-to-br from-white via-sky-50/50 to-emerald-50/40 p-6 shadow-xl shadow-slate-200/40 backdrop-blur-sm sm:p-8">
                    <div className="mb-1 flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-sky-600" />
                        <span className="text-xs font-semibold text-sky-700 uppercase tracking-widest">
                            AI Document Processing
                        </span>
                    </div>
                    <h1 className="text-3xl font-bold text-gray-900 sm:text-4xl">Upload Documents</h1>
                    <p className="mt-2 max-w-2xl text-gray-500">
                        Drag, drop, and launch extraction from a single workspace designed for supplier operations.
                    </p>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-1">
                    <SummaryCard
                        icon={FolderOpen}
                        label="Upload Queue"
                        value={`${files.length} file${files.length > 1 ? 's' : ''}`}
                        tone="bg-sky-50 text-sky-600"
                    />
                    <SummaryCard
                        icon={ShieldCheck}
                        label="Supported Types"
                        value="PDF, PNG, JPG"
                        tone="bg-emerald-50 text-emerald-600"
                    />
                    <SummaryCard
                        icon={Activity}
                        label="Pipeline Status"
                        value={processing ? 'Processing' : 'Ready'}
                        tone="bg-amber-50 text-amber-600"
                    />
                </div>
            </div>

            {errorMessage && (
                <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {errorMessage}
                </div>
            )}

            {statusMessage && (
                <div className={`mb-6 rounded-xl px-4 py-3 text-sm ${uploadedFiles.length > 0
                    ? 'border border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border border-sky-100 bg-sky-50 text-sky-700'
                    }`}>
                    <div className="flex items-center gap-2">
                        {uploadedFiles.length > 0 && <CheckCircle className="h-4 w-4" />}
                        {statusMessage}
                    </div>
                </div>
            )}

            {uploadedFiles.length > 0 && (
                <Card className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50/30 p-4">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">
                        Uploaded Files Response
                    </p>
                    <div className="space-y-2">
                        {uploadedFiles.map((file) => (
                            <div key={`${file.id}-${file.filename}`} className="flex items-center justify-between rounded-xl border border-emerald-100 bg-white px-3 py-2 text-sm">
                                <span className="font-medium text-slate-700">{file.filename}</span>
                                <span className="text-xs text-slate-500">{file.contentType || 'unknown type'}</span>
                            </div>
                        ))}
                    </div>
                </Card>
            )}

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_320px]">
                <div className="space-y-6">
                    <div
                        {...getRootProps()}
                        className={`border-2 border-dashed rounded-[28px] p-12 text-center cursor-pointer transition-all duration-200 select-none bg-white/95 shadow-lg ${isDragReject
                            ? 'border-red-400 bg-red-50'
                            : isDragActive
                                ? 'border-sky-500 bg-sky-50 scale-[1.01]'
                                : 'border-gray-200 bg-white hover:border-sky-300 hover:bg-sky-50/30'
                            }`}
                    >
                        <input {...getInputProps()} />
                        <div className="flex flex-col items-center gap-4 pointer-events-none">
                            <div
                                className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${isDragReject
                                    ? 'bg-red-100'
                                    : isDragActive
                                        ? 'bg-sky-100'
                                        : 'bg-gray-100'
                                    }`}
                            >
                                {isDragReject ? (
                                    <AlertCircle className="w-8 h-8 text-red-400" />
                                ) : (
                                    <Upload
                                        className={`w-8 h-8 ${isDragActive ? 'text-sky-500' : 'text-gray-400'}`}
                                    />
                                )}
                            </div>

                            {isDragReject ? (
                                <p className="text-base font-semibold text-red-500">Unsupported file type</p>
                            ) : isDragActive ? (
                                <p className="text-base font-semibold text-sky-700">Release to upload...</p>
                            ) : (
                                <>
                                    <div>
                                        <p className="text-base font-semibold text-gray-700">
                                            Drag and drop files here
                                        </p>
                                        <p className="text-sm text-gray-400 mt-1">
                                            or{' '}
                                            <span className="text-sky-600 underline underline-offset-2 cursor-pointer">
                                                browse from your computer
                                            </span>
                                        </p>
                                    </div>
                                    <div className="flex flex-wrap justify-center gap-2">
                                        {['PDF', 'PNG', 'JPG', 'TIFF', 'DOCX'].map((ext) => (
                                            <span
                                                key={ext}
                                                className="text-xs bg-gray-100 text-gray-500 px-2.5 py-1 rounded-full font-medium"
                                            >
                                                {ext}
                                            </span>
                                        ))}
                                    </div>
                                </>
                            )}
                        </div>
                    </div>

                    {files.length > 0 && (
                        <Card className="space-y-3 rounded-[28px] p-5">
                            <div className="flex items-center justify-between px-1">
                                <h3 className="text-sm font-semibold text-gray-700">
                                    {files.length} file{files.length > 1 ? 's' : ''} selected
                                </h3>
                                <Button
                                    onClick={clearAll}
                                    variant="ghost"
                                    size="sm"
                                    className="!h-8 border-red-200 text-red-600 hover:border-red-300"
                                >
                                    Clear all
                                </Button>
                            </div>
                            <div className="space-y-2">
                                {files.map((file) => (
                                    <FileCard key={file.name} file={file} onRemove={removeFile} />
                                ))}
                            </div>
                        </Card>
                    )}
                </div>

                <Card className="rounded-[28px] p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-gray-400">Workflow</p>
                    <div className="mt-4 space-y-4">
                        {[
                            { step: '1', title: 'Upload', description: 'Send raw files to the ingestion API.' },
                            { step: '2', title: 'Process', description: 'Launch extraction and validation tasks.' },
                            { step: '3', title: 'Review', description: 'Open results and supplier CRM dashboards.' },
                        ].map((item) => (
                            <div key={item.step} className="flex gap-3 rounded-2xl bg-slate-50 p-4">
                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-600 text-xs font-bold text-white">
                                    {item.step}
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                                    <p className="mt-1 text-xs leading-5 text-slate-500">{item.description}</p>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="mt-6 rounded-2xl border border-dashed border-sky-200 bg-sky-50/70 p-4 text-sm text-sky-700">
                        {processing ? statusMessage || 'Processing in progress...' : 'Pipeline ready for a new batch.'}
                    </div>

                    <div className="mt-6 space-y-3 rounded-2xl border border-slate-100 bg-white p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-500">Document Metadata</p>

                        <div>
                            <label className="mb-1 block text-xs font-semibold text-slate-600">Document Type</label>
                            <select
                                value={formState.documentType}
                                onChange={(e) => updateFormField('documentType', e.target.value)}
                                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                            >
                                {DOCUMENT_TYPES.map((type) => (
                                    <option key={type.value} value={type.value}>{type.label}</option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="mb-1 block text-xs font-semibold text-slate-600">Supplier Name</label>
                            <input
                                type="text"
                                value={formState.supplierName}
                                onChange={(e) => updateFormField('supplierName', e.target.value)}
                                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                placeholder="e.g. ACME Corporation"
                            />
                            {formErrors.supplierName && <p className="mt-1 text-xs text-red-600">{formErrors.supplierName}</p>}
                        </div>

                        {(formState.documentType === 'invoice' || formState.documentType === 'quote') && (
                            <div>
                                <label className="mb-1 block text-xs font-semibold text-slate-600">Amount</label>
                                <input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={formState.amount}
                                    onChange={(e) => updateFormField('amount', e.target.value)}
                                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                    placeholder="0.00"
                                />
                                {formErrors.amount && <p className="mt-1 text-xs text-red-600">{formErrors.amount}</p>}
                            </div>
                        )}

                        {formState.documentType === 'invoice' && (
                            <>
                                <div>
                                    <label className="mb-1 block text-xs font-semibold text-slate-600">Invoice Number</label>
                                    <input
                                        type="text"
                                        value={formState.invoiceNumber}
                                        onChange={(e) => updateFormField('invoiceNumber', e.target.value)}
                                        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                        placeholder="INV-2026-001"
                                    />
                                    {formErrors.invoiceNumber && <p className="mt-1 text-xs text-red-600">{formErrors.invoiceNumber}</p>}
                                </div>
                                <div>
                                    <label className="mb-1 block text-xs font-semibold text-slate-600">Invoice Date</label>
                                    <input
                                        type="date"
                                        value={formState.invoiceDate}
                                        onChange={(e) => updateFormField('invoiceDate', e.target.value)}
                                        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                    />
                                    {formErrors.invoiceDate && <p className="mt-1 text-xs text-red-600">{formErrors.invoiceDate}</p>}
                                </div>
                            </>
                        )}

                        {formState.documentType === 'quote' && (
                            <>
                                <div>
                                    <label className="mb-1 block text-xs font-semibold text-slate-600">Quote Reference</label>
                                    <input
                                        type="text"
                                        value={formState.quoteReference}
                                        onChange={(e) => updateFormField('quoteReference', e.target.value)}
                                        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                        placeholder="QTE-2026-017"
                                    />
                                    {formErrors.quoteReference && <p className="mt-1 text-xs text-red-600">{formErrors.quoteReference}</p>}
                                </div>
                                <div>
                                    <label className="mb-1 block text-xs font-semibold text-slate-600">Valid Until</label>
                                    <input
                                        type="date"
                                        value={formState.validUntil}
                                        onChange={(e) => updateFormField('validUntil', e.target.value)}
                                        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                    />
                                    {formErrors.validUntil && <p className="mt-1 text-xs text-red-600">{formErrors.validUntil}</p>}
                                </div>
                            </>
                        )}

                        {formState.documentType === 'certificate' && (
                            <>
                                <div>
                                    <label className="mb-1 block text-xs font-semibold text-slate-600">Certificate Type</label>
                                    <input
                                        type="text"
                                        value={formState.certificateType}
                                        onChange={(e) => updateFormField('certificateType', e.target.value)}
                                        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                        placeholder="ISO 9001"
                                    />
                                    {formErrors.certificateType && <p className="mt-1 text-xs text-red-600">{formErrors.certificateType}</p>}
                                </div>
                                <div>
                                    <label className="mb-1 block text-xs font-semibold text-slate-600">Issuer</label>
                                    <input
                                        type="text"
                                        value={formState.issuer}
                                        onChange={(e) => updateFormField('issuer', e.target.value)}
                                        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                        placeholder="Certification Body"
                                    />
                                    {formErrors.issuer && <p className="mt-1 text-xs text-red-600">{formErrors.issuer}</p>}
                                </div>
                                <label className="flex items-center gap-2 text-sm text-slate-700">
                                    <input
                                        type="checkbox"
                                        checked={formState.hasExpiry}
                                        onChange={(e) => {
                                            updateFormField('hasExpiry', e.target.checked);
                                            if (!e.target.checked) {
                                                updateFormField('expiryDate', '');
                                            }
                                        }}
                                        className="h-4 w-4 rounded border-gray-300 text-sky-600"
                                    />
                                    This certificate has an expiry date
                                </label>
                                {formState.hasExpiry && (
                                    <div>
                                        <label className="mb-1 block text-xs font-semibold text-slate-600">Expiry Date</label>
                                        <input
                                            type="date"
                                            value={formState.expiryDate}
                                            onChange={(e) => updateFormField('expiryDate', e.target.value)}
                                            className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                        />
                                        {formErrors.expiryDate && <p className="mt-1 text-xs text-red-600">{formErrors.expiryDate}</p>}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </Card>
            </div>

            <Card className="mt-8 flex flex-col gap-4 rounded-[28px] p-5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-gray-400">
                    {files.length === 0
                        ? 'Add files to get started'
                        : `Ready to process ${files.length} document${files.length > 1 ? 's' : ''}`}
                </p>
                <Button
                    onClick={handleProcess}
                    disabled={files.length === 0 || processing}
                    variant="primary"
                    size="lg"
                >
                    {processing ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            {statusMessage || 'Processing...'}
                        </>
                    ) : (
                        <>
                            <Play className="w-4 h-4" />
                            Start Processing
                        </>
                    )}
                </Button>
            </Card>
        </div>
    );
}

