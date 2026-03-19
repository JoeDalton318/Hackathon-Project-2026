function cn(...classes) {
    return classes.filter(Boolean).join(' ');
}

export default function Card({ className = '', children, ...props }) {
    return (
        <section
            className={cn('rounded-card border border-slate-100 bg-background-elevated shadow-card', className)}
            {...props}
        >
            {children}
        </section>
    );
}

export function CardHeader({ className = '', children }) {
    return <div className={cn('border-b border-slate-100 px-5 py-4', className)}>{children}</div>;
}

export function CardBody({ className = '', children }) {
    return <div className={cn('px-5 py-4', className)}>{children}</div>;
}

export function CardTitle({ className = '', children }) {
    return <h3 className={cn('font-display text-base font-bold text-ink', className)}>{children}</h3>;
}
