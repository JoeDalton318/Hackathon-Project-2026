const VARIANT_CLASSES = {
    validated: 'border border-success/25 bg-success-soft text-success-text',
    success: 'border border-success/25 bg-success-soft text-success-text',
    inconsistent: 'border border-error/25 bg-error-soft text-error-text',
    error: 'border border-error/25 bg-error-soft text-error-text',
    warning: 'border border-warning/25 bg-warning-soft text-warning-text',
    info: 'border border-primary/20 bg-primary-soft text-primary-dark',
    neutral: 'border border-slate-200 bg-slate-100 text-slate-700',
};

function cn(...classes) {
    return classes.filter(Boolean).join(' ');
}

export default function Badge({ variant = 'neutral', icon: Icon, children, className = '' }) {
    return (
        <span
            className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold',
                VARIANT_CLASSES[variant] || VARIANT_CLASSES.neutral,
                className
            )}
        >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {children}
        </span>
    );
}
