import { useEffect, useState } from 'react';
import {
    Search,
    Plus,
    Building2,
    X,
    Users,
    FileText,
    CheckCircle,
    ShieldAlert,
    ShieldCheck,
    Eye,
    Sparkles,
} from 'lucide-react';
import { getApiErrorMessage } from '../services/apiClient';
import { getDocuments, getSuppliers } from '../services/documentService';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Card, { CardBody, CardHeader } from '../components/ui/Card';
import Table, { TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/Table';

const COMPLIANCE_CONFIG = {
    compliant: {
        label: 'Compliant',
        variant: 'success',
        icon: ShieldCheck,
    },
    review: {
        label: 'Review',
        variant: 'warning',
        icon: Eye,
    },
    nonCompliant: {
        label: 'Non-compliant',
        variant: 'error',
        icon: ShieldAlert,
    },
};

function getComplianceStatus(documents) {
    if (documents.some((document) => document.validationStatus === 'inconsistent')) {
        return 'nonCompliant';
    }

    if (documents.some((document) => document.validationStatus === 'review')) {
        return 'review';
    }

    return 'compliant';
}

function ComplianceBadge({ status }) {
    const config = COMPLIANCE_CONFIG[status] || COMPLIANCE_CONFIG.review;
    const Icon = config.icon;

    return <Badge variant={config.variant} icon={Icon}>{config.label}</Badge>;
}

const EMPTY_FORM = {
    name: '',
    siren: '',
    category: '',
    country: '',
    contactEmail: '',
    contactPhone: '',
};

const FORM_FIELDS = [
    { key: 'name', label: 'Company Name', placeholder: 'e.g. Acme Corp', type: 'text' },
    { key: 'siren', label: 'SIREN', placeholder: 'e.g. 123456789', type: 'text' },
    { key: 'category', label: 'Category', placeholder: 'e.g. Office Supplies', type: 'text' },
    { key: 'country', label: 'Country', placeholder: 'e.g. France', type: 'text' },
    { key: 'contactEmail', label: 'Contact Email', placeholder: 'contact@company.com', type: 'email' },
    { key: 'contactPhone', label: 'Contact Phone', placeholder: '+33 1 23 45 67 89', type: 'tel' },
];

function LoadingMetricCard() {
    return (
        <Card className="p-5">
            <div className="animate-pulse">
                <div className="h-3 w-24 rounded bg-slate-200" />
                <div className="mt-4 h-8 w-16 rounded bg-slate-200" />
            </div>
        </Card>
    );
}

function LoadingSupplierCards() {
    return (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
                <Card key={index} className="p-5">
                    <div className="animate-pulse space-y-4">
                        <div className="h-5 w-40 rounded bg-slate-200" />
                        <div className="grid grid-cols-3 gap-3">
                            <div className="h-16 rounded-xl bg-slate-100" />
                            <div className="h-16 rounded-xl bg-slate-100" />
                            <div className="h-16 rounded-xl bg-slate-100" />
                        </div>
                        <div className="space-y-2">
                            <div className="h-10 rounded-xl bg-slate-100" />
                            <div className="h-10 rounded-xl bg-slate-100" />
                            <div className="h-10 rounded-xl bg-slate-100" />
                        </div>
                    </div>
                </Card>
            ))}
        </div>
    );
}

function SupplierCard({ supplier }) {
    return (
        <Card className="overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl">
            <CardHeader className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-100">
                        <Building2 className="h-5 w-5 text-sky-600" />
                    </div>
                    <div>
                        <h3 className="text-base font-bold text-gray-900">{supplier.name}</h3>
                        <p className="mt-1 text-xs uppercase tracking-wide text-gray-400">SIREN {supplier.siren || 'Not available'}</p>
                    </div>
                </div>
                <ComplianceBadge status={supplier.complianceStatus} />
            </CardHeader>

            <CardBody className="grid grid-cols-3 gap-3 px-5 py-4">
                <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <p className="text-xs text-gray-400">Documents</p>
                    <p className="mt-1 text-lg font-bold text-gray-900">{supplier.documents.length}</p>
                </div>
                <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <p className="text-xs text-gray-400">Compliance</p>
                    <p className="mt-1 text-sm font-semibold text-gray-900">{COMPLIANCE_CONFIG[supplier.complianceStatus]?.label}</p>
                </div>
                <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <p className="text-xs text-gray-400">Total Amount</p>
                    <p className="mt-1 text-sm font-semibold text-gray-900">
                        {supplier.totalAmount.toLocaleString('fr-FR')} {supplier.currency}
                    </p>
                </div>
            </CardBody>

            <div className="px-5 pb-5">
                <Table minWidthClass="min-w-0" className="rounded-xl shadow-none">
                    <TableHead>
                        <tr className="bg-gray-50">
                            <TableHeader className="px-3 py-2 text-[11px]">Document</TableHeader>
                            <TableHeader className="px-3 py-2 text-[11px]">Type</TableHeader>
                            <TableHeader className="px-3 py-2 text-[11px]">Validation</TableHeader>
                        </tr>
                    </TableHead>
                    <TableBody>
                        {supplier.documents.length > 0 ? (
                            supplier.documents.map((document) => (
                                <TableRow key={document.id} className="align-top">
                                    <TableCell className="px-3 py-2 text-gray-700">{document.filename}</TableCell>
                                    <TableCell className="px-3 py-2 capitalize">{document.documentType}</TableCell>
                                    <TableCell className="px-3 py-2">
                                        <Badge variant={document.validationStatus === 'inconsistent'
                                            ? 'error'
                                            : document.validationStatus === 'review'
                                                ? 'warning'
                                                : 'success'}>
                                            {document.validationStatus}
                                        </Badge>
                                    </TableCell>
                                </TableRow>
                            ))
                        ) : (
                            <tr>
                                <td colSpan="3" className="px-3 py-4 text-sm text-gray-400">
                                    No linked documents yet.
                                </td>
                            </tr>
                        )}
                    </TableBody>
                </Table>
            </div>
        </Card>
    );
}

export default function SupplierCRMPage() {
    const [suppliers, setSuppliers] = useState([]);
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [search, setSearch] = useState('');
    const [filter, setFilter] = useState('all');
    const [showModal, setShowModal] = useState(false);
    const [form, setForm] = useState(EMPTY_FORM);

    useEffect(() => {
        let isActive = true;

        async function loadData() {
            setLoading(true);
            setLoadError('');

            const [suppliersResult, documentsResult] = await Promise.allSettled([
                getSuppliers(),
                getDocuments(),
            ]);

            if (!isActive) {
                return;
            }

            const errorMessages = [];

            if (suppliersResult.status === 'fulfilled' && Array.isArray(suppliersResult.value)) {
                setSuppliers(suppliersResult.value);
                if (suppliersResult.value.length === 0) {
                    errorMessages.push('No suppliers found yet for this account.');
                }
            } else {
                setSuppliers([]);
                const supplierReason = suppliersResult.status === 'rejected'
                    ? getApiErrorMessage(suppliersResult.reason, 'Unable to load suppliers.')
                    : 'Suppliers API returned invalid data.';
                errorMessages.push(supplierReason);
            }

            if (documentsResult.status === 'fulfilled' && Array.isArray(documentsResult.value)) {
                setDocuments(documentsResult.value);
                if (documentsResult.value.length === 0) {
                    errorMessages.push('No documents found yet for this account.');
                }
            } else {
                setDocuments([]);
                const documentReason = documentsResult.status === 'rejected'
                    ? getApiErrorMessage(documentsResult.reason, 'Unable to load documents.')
                    : 'Documents API returned invalid data.';
                errorMessages.push(documentReason);
            }

            setLoadError(errorMessages.join(' '));

            setLoading(false);
        }

        loadData();

        return () => {
            isActive = false;
        };
    }, []);

    const supplierRecords = suppliers.map((supplier) => {
        const linkedDocuments = documents.filter((document) => document.supplier === supplier.name);
        const siren = supplier.siren || linkedDocuments[0]?.siren || 'Not available';
        const totalAmount = linkedDocuments.length > 0
            ? linkedDocuments.reduce((sum, document) => sum + (document.extractedAmount || 0), 0)
            : supplier.totalAmount;
        const currency = linkedDocuments[0]?.currency || supplier.currency || 'EUR';

        return {
            ...supplier,
            siren,
            documents: linkedDocuments,
            currency,
            totalAmount,
            complianceStatus: getComplianceStatus(linkedDocuments),
        };
    });

    const filtered = supplierRecords.filter((s) => {
        const q = search.toLowerCase();
        const matchesSearch =
            s.name.toLowerCase().includes(q) ||
            s.siren.toLowerCase().includes(q) ||
            s.documents.some((document) => document.filename.toLowerCase().includes(q));
        const matchesFilter = filter === 'all' || s.complianceStatus === filter;
        return matchesSearch && matchesFilter;
    });

    const totalValue = supplierRecords.reduce((sum, s) => sum + s.totalAmount, 0);
    const compliantCount = supplierRecords.filter((s) => s.complianceStatus === 'compliant').length;
    const totalDocs = supplierRecords.reduce((sum, s) => sum + s.documents.length, 0);
    const flaggedCount = supplierRecords.filter((s) => s.complianceStatus === 'nonCompliant').length;

    const handleAdd = () => {
        if (!form.name.trim()) return;
        const newSupplier = {
            id: Date.now(),
            ...form,
            documentCount: 0,
            totalAmount: 0,
            currency: 'EUR',
            lastActivity: new Date().toISOString().slice(0, 10),
            status: 'active',
            reliability: 100,
        };
        setSuppliers((prev) => [newSupplier, ...prev]);
        setForm(EMPTY_FORM);
        setShowModal(false);
    };

    return (
        <div className="saas-fade-in p-4 sm:p-6 lg:p-8">
            <div className="saas-rise mb-8 flex flex-col gap-4 rounded-[28px] border border-sky-100 bg-gradient-to-br from-white via-sky-50/50 to-emerald-50/40 p-6 shadow-xl shadow-slate-200/40 sm:p-8 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">
                        <Sparkles className="h-3.5 w-3.5" />
                        Vendor Intelligence
                    </div>
                    <h1 className="text-3xl font-bold text-gray-900">Supplier CRM</h1>
                    <p className="mt-2 max-w-3xl text-gray-500">
                        Track supplier identity, linked documents, and compliance posture.
                    </p>
                </div>
                <Button
                    onClick={() => setShowModal(true)}
                    variant="primary"
                    className="flex-shrink-0"
                >
                    <Plus className="w-4 h-4" />
                    Add Supplier
                </Button>
            </div>

            {loadError && (
                <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {loadError}
                </div>
            )}

            {loading ? (
                <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <LoadingMetricCard key={index} />
                    ))}
                </div>
            ) : (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    {[
                        { label: 'Total Suppliers', value: supplierRecords.length, icon: Users, bg: 'bg-sky-50', text: 'text-sky-600' },
                        { label: 'Compliant', value: compliantCount, icon: CheckCircle, bg: 'bg-emerald-50', text: 'text-emerald-600' },
                        { label: 'Total Documents', value: totalDocs, icon: FileText, bg: 'bg-blue-50', text: 'text-blue-600' },
                        { label: 'Flagged Suppliers', value: flaggedCount, icon: ShieldAlert, bg: 'bg-red-50', text: 'text-red-600' },
                    ].map(({ label, value, icon: Icon, bg, text }) => (
                        <Card key={label} className="flex items-center justify-between rounded-xl p-5 shadow-soft">
                            <div>
                                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
                                <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
                                {label === 'Flagged Suppliers' && (
                                    <p className="mt-1 text-xs text-gray-400">{totalValue.toLocaleString('fr-FR')} € tracked</p>
                                )}
                            </div>
                            <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${bg}`}>
                                <Icon className={`w-5 h-5 ${text}`} />
                            </div>
                        </Card>
                    ))}
                </div>
            )}

            {/* Search & filter */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-6">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search by company, SIREN or document…"
                        className="w-full pl-10 pr-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500 shadow-sm"
                    />
                </div>
                <div className="flex gap-2">
                    {['all', 'compliant', 'review', 'nonCompliant'].map((f) => (
                        <Button
                            key={f}
                            onClick={() => setFilter(f)}
                            variant={filter === f ? 'primary' : 'ghost'}
                            size="sm"
                            className="capitalize"
                        >
                            {f === 'all' ? 'All' : COMPLIANCE_CONFIG[f]?.label || f}
                        </Button>
                    ))}
                </div>
            </div>

            <Table className="mb-8" minWidthClass="min-w-[720px]">
                <TableHead>
                    <tr className="bg-gray-50 border-b border-gray-100">
                        <TableHeader>Company Name</TableHeader>
                        <TableHeader>SIREN</TableHeader>
                        <TableHeader>Documents</TableHeader>
                        <TableHeader>Compliance Status</TableHeader>
                    </tr>
                </TableHead>
                <TableBody className="divide-y divide-gray-50">
                    {filtered.map((supplier) => (
                        <TableRow key={supplier.id}>
                            <TableCell className="font-semibold text-gray-900">{supplier.name}</TableCell>
                            <TableCell className="font-mono text-gray-600">{supplier.siren}</TableCell>
                            <TableCell>
                                {supplier.documents.length > 0
                                    ? supplier.documents.map((document) => document.filename).join(', ')
                                    : 'No linked documents'}
                            </TableCell>
                            <TableCell><ComplianceBadge status={supplier.complianceStatus} /></TableCell>
                        </TableRow>
                    ))}
                </TableBody>
                {filtered.length === 0 && !loading && (
                    <tfoot>
                        <tr>
                            <td colSpan={4} className="px-5 py-12 text-center text-sm text-gray-400">
                                No suppliers match your search/filter.
                            </td>
                        </tr>
                    </tfoot>
                )}
            </Table>

            {loading ? (
                <LoadingSupplierCards />
            ) : filtered.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                    {filtered.map((s) => (
                        <SupplierCard key={s.id} supplier={s} />
                    ))}
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                    <Building2 className="w-10 h-10 mb-3" />
                    <p className="text-sm font-medium">No suppliers found.</p>
                    <p className="text-xs mt-1">Try adjusting your search or filters.</p>
                </div>
            )}

            {/* Add Supplier Modal */}
            {showModal && (
                <div
                    className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
                    onClick={(e) => e.target === e.currentTarget && setShowModal(false)}
                >
                    <Card className="w-full max-w-md rounded-2xl">
                        {/* Modal header */}
                        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100">
                            <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-xl bg-sky-50 flex items-center justify-center">
                                    <Building2 className="w-4 h-4 text-sky-600" />
                                </div>
                                <h2 className="text-base font-bold text-gray-900">Add New Supplier</h2>
                            </div>
                            <button
                                onClick={() => setShowModal(false)}
                                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Modal body */}
                        <div className="px-6 py-5 space-y-4">
                            {FORM_FIELDS.map(({ key, label, placeholder, type }) => (
                                <div key={key}>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                                        {label}
                                        {key === 'name' && <span className="text-red-400 ml-0.5">*</span>}
                                    </label>
                                    <input
                                        type={type}
                                        placeholder={placeholder}
                                        value={form[key]}
                                        onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                                        className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500 transition-shadow"
                                    />
                                </div>
                            ))}
                        </div>

                        {/* Modal footer */}
                        <div className="px-6 py-4 border-t border-gray-50 flex gap-3">
                            <Button
                                onClick={() => { setShowModal(false); setForm(EMPTY_FORM); }}
                                variant="ghost"
                                className="flex-1"
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleAdd}
                                disabled={!form.name.trim()}
                                variant="primary"
                                className="flex-1"
                            >
                                Add Supplier
                            </Button>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
}

