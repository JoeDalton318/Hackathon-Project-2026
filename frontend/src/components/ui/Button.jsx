const VARIANT_CLASSES = {
    primary: 'bg-primary text-white hover:bg-primary-dark shadow-soft',
    secondary: 'bg-secondary text-white hover:bg-secondary-dark shadow-soft',
    ghost: 'border border-slate-200 bg-white text-ink hover:border-primary/40 hover:text-primary',
    danger: 'bg-error text-white hover:bg-error/90 shadow-soft',
};

const SIZE_CLASSES = {
    sm: 'h-9 px-3 text-xs',
    md: 'h-11 px-4 text-sm',
    lg: 'h-12 px-6 text-sm',
};

function cn(...classes) {
    return classes.filter(Boolean).join(' ');
}

export default function Button({
    as,
    variant = 'primary',
    size = 'md',
    className = '',
    children,
    ...props
}) {
    const Component = as || 'button';

    return (
        <Component
            className={cn(
                'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50',
                VARIANT_CLASSES[variant] || VARIANT_CLASSES.primary,
                SIZE_CLASSES[size] || SIZE_CLASSES.md,
                className
            )}
            {...props}
        >
            {children}
        </Component>
    );
}
