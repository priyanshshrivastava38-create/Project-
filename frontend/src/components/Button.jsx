import Icon from './Icon';

export default function Button({
  children, variant = 'secondary', size = 'md', type = 'button', loading = false, disabled = false,
  icon, className = '', ...rest
}) {
  return (
    <button
      type={type}
      className={`btn btn-${variant} btn-${size} ${className}`.trim()}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className="spinner spinner-xs" aria-hidden="true" /> : icon ? <Icon name={icon} size={16} /> : null}
      {children ? <span>{children}</span> : null}
    </button>
  );
}
