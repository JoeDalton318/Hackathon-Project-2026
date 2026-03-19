import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu, Sparkles } from 'lucide-react';
import Sidebar from './Sidebar';

const PAGE_META = {
    '/': {
        title: 'Upload Workspace',
        subtitle: 'Ingest and queue new supplier documents for extraction.',
    },
    '/results': {
        title: 'Documents Dashboard',
        subtitle: 'Monitor extracted fields, validation signals, and inconsistencies.',
    },
    '/suppliers': {
        title: 'Supplier CRM',
        subtitle: 'Review supplier identity, linked documents, and compliance posture.',
    },
};

export default function Layout() {
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const location = useLocation();
    const currentMeta = PAGE_META[location.pathname] || PAGE_META['/'];

    return (
        <div className="min-h-screen overflow-hidden">
            <div className="relative flex min-h-screen">
                <div
                    onClick={() => setMobileNavOpen(false)}
                    className={`fixed inset-0 z-30 bg-slate-950/45 backdrop-blur-sm transition lg:hidden ${mobileNavOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'}`}
                />

                <Sidebar
                    className={`fixed inset-y-0 left-0 z-40 transition-transform duration-300 lg:static lg:translate-x-0 ${mobileNavOpen ? 'translate-x-0' : '-translate-x-full'}`}
                    onNavigate={() => setMobileNavOpen(false)}
                    onClose={() => setMobileNavOpen(false)}
                />

                <div className="flex min-w-0 flex-1 flex-col">
                    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
                        <div className="flex items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
                            <div className="flex min-w-0 items-center gap-3">
                                <button
                                    onClick={() => setMobileNavOpen(true)}
                                    className="rounded-2xl border border-slate-200 bg-white p-2.5 text-slate-600 shadow-sm transition hover:border-primary/30 hover:text-primary-dark lg:hidden"
                                >
                                    <Menu className="h-5 w-5" />
                                </button>
                                <div className="min-w-0">
                                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary-dark">Control Center</p>
                                    <h2 className="truncate text-xl font-bold text-slate-900 sm:text-2xl">{currentMeta.title}</h2>
                                    <p className="hidden text-sm text-slate-500 sm:block">{currentMeta.subtitle}</p>
                                </div>
                            </div>

                            <div className="hidden items-center gap-2 rounded-full border border-success/20 bg-success-soft px-3 py-2 text-xs font-semibold text-success-text shadow-sm sm:flex">
                                <Sparkles className="h-3.5 w-3.5" />
                                Operational workspace online
                            </div>
                        </div>
                    </header>

                    <main className="relative flex-1 overflow-y-auto">
                        <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-primary-soft/70 to-transparent" />
                        <div className="pointer-events-none absolute right-10 top-8 h-44 w-44 rounded-full bg-primary-soft/60 blur-3xl" />
                        <div className="pointer-events-none absolute left-20 top-24 h-52 w-52 rounded-full bg-secondary-soft/70 blur-3xl" />
                        <Outlet />
                    </main>
                </div>
            </div>
        </div>
    );
}
