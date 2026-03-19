import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Upload, FileText, Users, Brain, BarChart3, X, Sparkles, LogOut } from 'lucide-react';
import { logout } from '../services/auth';
import { disconnectWebSocket } from '../services/ws';

export const navItems = [
    { to: '/', label: 'Upload', icon: Upload, end: true },
    { to: '/results', label: 'Document Results', icon: FileText, end: false },
    { to: '/suppliers', label: 'Supplier CRM', icon: Users, end: false },
];

export default function Sidebar({ className = '', onNavigate, onClose }) {
    const navigate = useNavigate();
    const [isDisconnecting, setIsDisconnecting] = useState(false);

    async function handleDisconnect() {
        if (isDisconnecting) {
            return;
        }

        setIsDisconnecting(true);
        await logout();
        disconnectWebSocket();
        setIsDisconnecting(false);
        navigate('/login', { replace: true });
    }

    return (
        <aside className={`flex h-full w-72 flex-col border-r border-slate-800/80 bg-slate-900/95 backdrop-blur-xl ${className}`}>
            <div className="border-b border-slate-800/90 px-5 py-5">
                <div className="mb-4 flex items-center justify-between lg:hidden">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">Navigation</span>
                    <button
                        onClick={onClose}
                        className="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-sky-950/30">
                        <Brain className="h-5 w-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-base font-bold leading-none text-white">DocAI</h1>
                        <p className="mt-1 text-xs text-slate-400">Operations Platform</p>
                    </div>
                </div>
            </div>

            <nav className="flex-1 space-y-6 px-3 py-4">
                <div>
                    <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-widest text-slate-600">
                        Workspace
                    </p>
                    <div className="space-y-1">
                        {navItems.map(({ to, label, icon: Icon, end }) => (
                            <NavLink
                                key={to}
                                to={to}
                                end={end}
                                onClick={onNavigate}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-all duration-150 ${isActive
                                        ? 'bg-primary text-white shadow-lg shadow-sky-950/30'
                                        : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                                    }`
                                }
                            >
                                <Icon className="h-4 w-4 flex-shrink-0" />
                                {label}
                            </NavLink>
                        ))}
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-700 bg-slate-800/80 p-4 text-slate-300 shadow-inner shadow-black/20">
                    <div className="mb-3 flex items-center gap-2 text-secondary-soft">
                        <Sparkles className="h-4 w-4" />
                        <span className="text-xs font-semibold uppercase tracking-[0.24em]">Ops Pulse</span>
                    </div>
                    <p className="text-sm font-medium text-white">Operational dashboard</p>
                    <p className="mt-2 text-xs leading-5 text-slate-400">
                        Upload, validate, and review extracted supplier data from one place.
                    </p>
                </div>
            </nav>

            <div className="border-t border-slate-800 px-4 py-4">
                <button
                    onClick={handleDisconnect}
                    disabled={isDisconnecting}
                    className="mb-3 flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2.5 text-sm font-medium text-slate-200 transition hover:border-red-400/50 hover:bg-red-500/10 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    <LogOut className="h-4 w-4" />
                    {isDisconnecting ? 'Disconnecting...' : 'Disconnect'}
                </button>

                <div className="flex items-center gap-2 text-slate-500">
                    <BarChart3 className="h-3.5 w-3.5" />
                    <span className="text-xs">Hackathon 2026 - v1.0</span>
                </div>
            </div>
        </aside>
    );
}
