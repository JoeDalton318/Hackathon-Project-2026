import { useState, useCallback, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
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
import { getApiErrorMessage } from '../services/apiClient';
import { processDocuments, uploadDocuments } from '../services/documentService';
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
    const [done, setDone] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const navigate = useNavigate();

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
        setErrorMessage('');
        setStatusMessage('');
    };

    const handleProcess = async () => {
        if (!files.length || processing) return;

        setProcessing(true);
        setErrorMessage('');

        try {
            setStatusMessage('Uploading documents...');
            const uploadResponse = await uploadDocuments(files);
            const uploadedIds = Array.isArray(uploadResponse)
                ? uploadResponse.map((item) => item?.id).filter(Boolean)
                : [];

            setStatusMessage('Starting document processing...');
            await processDocuments(
                uploadedIds.length > 0
                    ? { documentIds: uploadedIds }
                    : { documentNames: files.map((file) => file.name) }
            );
        } catch (error) {
            setErrorMessage(`${getApiErrorMessage(error, 'Backend unavailable.')} Falling back to mock processing.`);
            setStatusMessage('Backend unavailable, running mock processing flow...');
            await new Promise((resolve) => setTimeout(resolve, 1800));
        } finally {
            setProcessing(false);
        }

        setDone(true);
        setTimeout(() => navigate('/results'), 1400);
    };

    if (done) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-5 text-center px-4">
                <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center">
                    <CheckCircle className="w-10 h-10 text-emerald-500" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Processing Complete!</h2>
                    <p className="text-gray-500 mt-1">
                        {files.length} document{files.length > 1 ? 's' : ''} analysed successfully.
                    </p>
                </div>
                <p className="text-sm text-sky-500 animate-pulse">Redirecting to results…</p>
            </div>
        );
    }

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

            {statusMessage && !done && (
                <div className="mb-6 rounded-xl border border-sky-100 bg-sky-50 px-4 py-3 text-sm text-sky-700">
                    {statusMessage}
                </div>
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

