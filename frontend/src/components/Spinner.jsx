export default function Spinner({ size = 'md', label = 'Loading…', inline = false }) {
  const el = <span className={`spinner spinner-${size}`} aria-hidden="true" />;
  if (inline) return el;
  return (
    <div className="spinner-wrap" role="status" aria-live="polite">
      {el}
      <span className="spinner-label">{label}</span>
    </div>
  );
}
