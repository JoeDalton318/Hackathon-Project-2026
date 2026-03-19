function cn(...classes) {
    return classes.filter(Boolean).join(' ');
}

export default function Table({ className = '', minWidthClass = 'min-w-[720px]', children }) {
    return (
        <div className={cn('overflow-hidden rounded-card border border-slate-100 bg-background-elevated shadow-card', className)}>
            <div className="overflow-x-auto">
                <table className={cn('w-full', minWidthClass)}>{children}</table>
            </div>
        </div>
    );
}

export function TableHead({ children }) {
    return <thead>{children}</thead>;
}

export function TableBody({ className = '', children }) {
    return <tbody className={cn('divide-y divide-slate-100', className)}>{children}</tbody>;
}

export function TableRow({ className = '', children }) {
    return <tr className={cn('hover:bg-slate-50/70', className)}>{children}</tr>;
}

export function TableHeader({ className = '', children }) {
    return (
        <th className={cn('px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-ink-subtle', className)}>
            {children}
        </th>
    );
}

export function TableCell({ className = '', children, ...props }) {
    return (
        <td className={cn('px-5 py-4 text-sm text-ink-muted', className)} {...props}>
            {children}
        </td>
    );
}
