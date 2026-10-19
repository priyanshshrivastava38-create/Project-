import { statusTone } from '../utils/status';
import { humanize } from '../utils/format';

export default function StatusBadge({ status, label, tone }) {
  if (!status && !label) return null;
  const t = tone || statusTone(status);
  return (
    <span className={`badge badge-${t}`} data-tone={t} title={status}>
      {label || humanize(status)}
    </span>
  );
}
