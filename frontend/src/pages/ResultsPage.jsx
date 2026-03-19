import { useEffect, useState } from 'react';
import { Search, AlertCircle, FileSearch, ShieldAlert, ShieldCheck, XCircle, Sparkles } from 'lucide-react';
import { getApiErrorMessage } from '../services/apiClient';
import { getDocuments } from '../services/documentService';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Card from '../components/ui/Card';
import Table, { TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/Table';

const VALIDATION_CONFIG = {
    validated: {
        label: 'Validated',
        variant: 'validated',
        icon: ShieldCheck,
    },
    review: {
        label: 'Needs review',
        variant: 'warning',
        icon: AlertCircle,
    },
    inconsistent: {
        label: 'Inconsistent',
        variant: 'inconsistent',
        icon: ShieldAlert,
    },
};

const VALIDATION_FILTERS = ['all', 'validated', 'review', 'inconsistent'];

function LoadingStatCard() {
    return (
        <Card className="p-5">
            <div className="animate-pulse">
                <div className="h-3 w-24 rounded bg-slate-200" />
                <div className="mt-4 h-8 w-20 rounded bg-slate-200" />
            </div>
        </Card>
    );
}

function LoadingTable() {
    return (
        <Card className="overflow-hidden">
            <div className="border-b border-gray-100 bg-gray-50 px-5 py-4">
                <div className="h-4 w-48 animate-pulse rounded bg-slate-200" />
            </div>
            <div className="space-y-3 p-5">
                {Array.from({ length: 6 }).map((_, index) => (
                    <div key={index} className="grid grid-cols-6 gap-3 animate-pulse">
                        <div className="col-span-2 h-10 rounded-xl bg-slate-100" />
                        <div className="h-10 rounded-xl bg-slate-100" />
                        <div className="h-10 rounded-xl bg-slate-100" />
                        <div className="h-10 rounded-xl bg-slate-100" />
                        <div className="h-10 rounded-xl bg-slate-100" />
                    </div>
                ))}
            </div>
        </Card>
    );
}

function StatusBadge({ status }) {
    const cfg = VALIDATION_CONFIG[status] || VALIDATION_CONFIG.review;
    const Icon = cfg.icon;

    return (
        <Badge variant={cfg.variant} icon={Icon}>{cfg.label}</Badge>
    );
}

function StatCard({ label, value, icon: Icon, bg, text }) {
    return (
        <Card className="flex items-center justify-between rounded-xl p-5">
            <div>
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
                <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
            </div>
            <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${bg}`}>
                <Icon className={`h-5 w-5 ${text}`} />
            </div>
        </Card>
    );
}

export default function ResultsPage() {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');

    useEffect(() => {
        let isActive = true;

        async function loadDocuments() {
            setLoading(true);
            setLoadError('');

            try {
                const data = await getDocuments();
                if (!isActive) {
                    return;
                }

                setDocuments(Array.isArray(data) ? data : []);
                if (!Array.isArray(data) || data.length === 0) {
                    setLoadError('Aucun document trouve en base pour ce compte.');
                }
            } catch (error) {
                if (!isActive) {
                    return;
                }

                setDocuments([]);
                setLoadError(getApiErrorMessage(error, 'Unable to load documents from backend API.'));
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        }

        loadDocuments();

        return () => {
            isActive = false;
        };
    }, []);

    const filtered = documents.filter((document) => {
        const query = search.toLowerCase();
        const matchesSearch =
            document.filename.toLowerCase().includes(query) ||
            document.documentType.toLowerCase().includes(query) ||
            `${document.siren || ''}`.toLowerCase().includes(query) ||
            `${document.siret || ''}`.toLowerCase().includes(query);
        const matchesStatus = statusFilter === 'all' || document.validationStatus === statusFilter;
        return matchesSearch && matchesStatus;
    });

    const counts = {
        total: documents.length,
        validated: documents.filter((document) => document.validationStatus === 'validated').length,
        inconsistent: documents.filter((document) => document.validationStatus === 'inconsistent').length,
        extractedTotal: documents.reduce((sum, document) => sum + (document.extractedAmount || 0), 0),
    };

    return (
        <div className="saas-fade-in p-4 sm:p-6 lg:p-8">
            <div className="saas-rise mb-8 rounded-[28px] border border-sky-100 bg-gradient-to-br from-white via-sky-50/50 to-emerald-50/40 p-6 shadow-xl shadow-slate-200/40 sm:p-8">
                <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">
                    <Sparkles className="h-3.5 w-3.5" />
                    Live Insights
                </div>
                <h1 className="text-3xl font-bold text-gray-900">Processed Documents Dashboard</h1>
                <p className="mt-2 max-w-3xl text-gray-500">
                    Review extracted fields and identify validation anomalies at a glance.
                </p>
            </div>

            {loadError && (
                <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {loadError}
                </div>
            )}

            {loading ? (
                <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <LoadingStatCard key={index} />
                    ))}
                </div>
            ) : (
                <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
                    <StatCard
                        label="Total Documents"
                        value={counts.total}
                        icon={FileSearch}
                        bg="bg-sky-50"
                        text="text-sky-600"
                    />
                    <StatCard
                        label="Validated"
                        value={counts.validated}
                        icon={ShieldCheck}
                        bg="bg-emerald-50"
                        text="text-emerald-600"
                    />
                    <StatCard
                        label="Inconsistencies"
                        value={counts.inconsistent}
                        icon={XCircle}
                        bg="bg-red-50"
                        text="text-red-600"
                    />
                    <StatCard
                        label="Extracted Total"
                        value={`${counts.extractedTotal.toLocaleString('fr-FR')} €`}
                        icon={AlertCircle}
                        bg="bg-amber-50"
                        text="text-amber-600"
                    />
                </div>
            )}

            <div className="mb-4 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
                <div className="relative w-full flex-1">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                    <input
                        type="text"
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder="Search by document name, type, SIREN or SIRET..."
                        className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-10 pr-4 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    {VALIDATION_FILTERS.map((filter) => (
                        <Button
                            key={filter}
                            onClick={() => setStatusFilter(filter)}
                            variant={statusFilter === filter ? 'primary' : 'ghost'}
                            size="sm"
                            className="capitalize"
                        >
                            {filter === 'all' ? 'All' : filter}
                        </Button>
                    ))}
                </div>
            </div>

            {loading ? (
                <LoadingTable />
            ) : (
                <Table minWidthClass="min-w-[920px]">
                    <TableHead>
                        <tr className="border-b border-gray-100 bg-gray-50">
                            <TableHeader>Document Name</TableHeader>
                            <TableHeader>Document Type</TableHeader>
                            <TableHeader>Extracted SIREN</TableHeader>
                            <TableHeader>Extracted SIRET</TableHeader>
                            <TableHeader className="text-right">Extracted Amount</TableHeader>
                            <TableHeader className="text-center">Validation Status</TableHeader>
                            <TableHeader>Notes</TableHeader>
                        </tr>
                    </TableHead>
                    <TableBody className="divide-y divide-gray-50">
                        {filtered.map((document) => {
                            const isInconsistent = document.validationStatus === 'inconsistent';

                            return (
                                <TableRow
                                    key={document.id}
                                    className={isInconsistent ? 'bg-red-50/60 hover:bg-red-50' : 'hover:bg-gray-50/60'}
                                >
                                    <TableCell>
                                        <div className="flex flex-col gap-1">
                                            <span className={`block max-w-[240px] truncate text-sm font-semibold ${isInconsistent ? 'text-red-700' : 'text-gray-700'}`}>
                                                {document.filename}
                                            </span>
                                            <span className="text-xs text-gray-400">{document.supplier}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={isInconsistent ? 'error' : 'neutral'} className="capitalize">
                                            {document.documentType}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className={`font-mono ${isInconsistent ? 'text-red-700' : 'text-gray-600'}`}>
                                        {document.siren}
                                    </TableCell>
                                    <TableCell className={`font-mono ${isInconsistent ? 'text-red-700' : 'text-gray-600'}`}>
                                        {document.siret}
                                    </TableCell>
                                    <TableCell className={`text-right font-semibold ${isInconsistent ? 'text-red-700' : 'text-gray-800'}`}>
                                        {document.extractedAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2 })}{' '}
                                        <span className="text-xs font-normal text-gray-400">{document.currency}</span>
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <StatusBadge status={document.validationStatus} />
                                    </TableCell>
                                    <TableCell>
                                        {(document.inconsistencies || []).length > 0 ? (
                                            <div className="flex flex-wrap gap-2">
                                                {(document.inconsistencies || []).map((item) => (
                                                    <Badge key={item} variant="error">{item}</Badge>
                                                ))}
                                                {document.amountSource && (
                                                    <span className="text-[11px] text-gray-500">Amount source: {document.amountSource}</span>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="flex flex-col gap-1">
                                                <Badge variant="success">No issue detected</Badge>
                                                {document.amountSource && (
                                                    <span className="text-[11px] text-gray-500">Amount source: {document.amountSource}</span>
                                                )}
                                            </div>
                                        )}
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>

                    {filtered.length === 0 && (
                        <tfoot>
                            <tr>
                                <td colSpan={7} className="px-5 py-16 text-center text-gray-400">
                                    <div className="flex flex-col items-center justify-center">
                                        <AlertCircle className="mb-2 h-8 w-8" />
                                        <p className="text-sm font-medium">No documents match your search.</p>
                                    </div>
                                </td>
                            </tr>
                        </tfoot>
                    )}

                    <tfoot>
                        <tr>
                            <td colSpan={7} className="border-t border-gray-50 bg-gray-50/50 px-5 py-3 text-xs text-gray-400">
                                Showing {filtered.length} of {documents.length} processed documents
                            </td>
                        </tr>
                    </tfoot>
                </Table>
            )}
        </div>
    );
}

