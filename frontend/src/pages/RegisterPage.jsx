import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Loader2, UserPlus, ShieldAlert } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { getAuthErrorMessage, isAuthenticated, register } from '../services/auth';

export default function RegisterPage() {
    const navigate = useNavigate();
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');

    if (isAuthenticated()) {
        return <Navigate to="/" replace />;
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setSubmitting(true);
        setErrorMessage('');

        try {
            await register(name, email, password);

            navigate('/login', {
                replace: true,
                state: {
                    from: '/upload',
                    registered: true,
                    email,
                },
            });
        } catch (error) {
            setErrorMessage(getAuthErrorMessage(error, 'Impossible de créer le compte. Veuillez réessayer.'));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-100 via-sky-50 to-emerald-50 px-4 py-10 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-md">
                <Card className="rounded-3xl border border-sky-100 p-8 shadow-xl shadow-slate-200/50">
                    <div className="mb-6 text-center">
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-700">Get Started</p>
                        <h1 className="mt-2 text-3xl font-bold text-slate-900">Create account</h1>
                        <p className="mt-2 text-sm text-slate-500">Register to access your document dashboard.</p>
                    </div>

                    {errorMessage && (
                        <div className="mb-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                            <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0" />
                            <span>{errorMessage}</span>
                        </div>
                    )}

                    <form className="space-y-4" onSubmit={handleSubmit}>
                        <div>
                            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">Name</label>
                            <input
                                type="text"
                                value={name}
                                onChange={(event) => setName(event.target.value)}
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500"
                                placeholder="John Doe"
                                required
                            />
                        </div>

                        <div>
                            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">Email</label>
                            <input
                                type="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500"
                                placeholder="you@company.com"
                                required
                            />
                        </div>

                        <div>
                            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">Password</label>
                            <input
                                type="password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500"
                                placeholder="Minimum 8 characters"
                                required
                            />
                        </div>

                        <Button type="submit" variant="primary" size="lg" className="w-full justify-center" disabled={submitting}>
                            {submitting ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Creating account...
                                </>
                            ) : (
                                <>
                                    <UserPlus className="h-4 w-4" />
                                    Register
                                </>
                            )}
                        </Button>
                    </form>

                    <p className="mt-5 text-center text-sm text-slate-500">
                        Already registered?{' '}
                        <Link to="/login" className="font-semibold text-sky-700 hover:text-sky-800">
                            Sign in
                        </Link>
                    </p>
                </Card>
            </div>
        </div>
    );
}
