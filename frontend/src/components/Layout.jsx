import { useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { LogOut, Menu, Sparkles } from 'lucide-react';
import Sidebar from './Sidebar';
import { apiBaseUrl, getApiErrorMessage, getApiRootStatus, getHealth } from '../services/api';
import { clearAuthToken } from '../services/auth';

const PAGE_META = {
    '/upload': {
        title: 'Upload Workspace',
        subtitle: 'Ingest and queue new supplier documents for extraction.',
    },
    '/dashboard': {
        title: 'Documents Dashboard',
        subtitle: 'Monitor extracted fields, validation signals, and inconsistencies.',
    },
    '/results': {
        title: 'Documents Dashboard',
        subtitle: 'Monitor extracted fields, validation signals, and inconsistencies.',
    },
    '/suppliers': {
        title: 'Supplier CRM',
        subtitle: 'Review supplier identity, linked documents, and compliance posture.',
    },
    '/crm': {
        title: 'Supplier CRM',
        subtitle: 'Review supplier identity, linked documents, and compliance posture.',
    },
};

export default function Layout() {
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const [apiConnected, setApiConnected] = useState(false);
    const [apiStatusLabel, setApiStatusLabel] = useState('API Down');
    const navigate = useNavigate();
    const location = useLocation();
    const currentMeta = PAGE_META[location.pathname] || PAGE_META['/dashboard'];

    function handleLogout() {
        clearAuthToken();
        navigate('/login', { replace: true });
    }

    useEffect(() => {
        let isMounted = true;

        async function checkHealth() {
            try {
                await Promise.all([getApiRootStatus(), getHealth()]);
                if (isMounted) {
                    setApiConnected(true);
                    setApiStatusLabel('API Connected');
                }
            } catch (error) {
                if (isMounted) {
                    setApiConnected(false);
                    setApiStatusLabel('API Down');
                    // Keep a clear message in console without breaking UI flow.
                    console.warn(getApiErrorMessage(error, 'Unable to reach API health endpoint.'), apiBaseUrl);
                }
            }
        }

        checkHealth();

        return () => {
            isMounted = false;
        };
    }, []);

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

                            <div className="hidden items-center gap-2 sm:flex">
                                <div className={`items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold shadow-sm sm:flex ${apiConnected
                                    ? 'border border-success/20 bg-success-soft text-success-text'
                                    : 'border border-error/20 bg-error-soft text-error-text'
                                    }`}>
                                    <Sparkles className="h-3.5 w-3.5" />
                                    {apiStatusLabel}
                                </div>
                                <button
                                    onClick={handleLogout}
                                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
                                >
                                    <LogOut className="h-3.5 w-3.5" />
                                    Deconnexion
                                </button>
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
