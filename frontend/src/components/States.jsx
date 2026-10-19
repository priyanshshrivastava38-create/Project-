import Button from './Button';
import Icon from './Icon';
import { errorMessage } from '../api/client';

export function EmptyState({ title = 'Nothing here yet', message, icon = 'box', action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon name={icon} size={28} /></div>
      <div className="empty-title">{title}</div>
      {message ? <p className="empty-msg">{message}</p> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = 'Could not load data' }) {
  const status = error?.status;
  const msg = status === 403 ? 'You do not have permission to view this data.' : errorMessage(error) || 'Unexpected error';
  return (
    <div className="error-state" role="alert">
      <div className="empty-icon error"><Icon name="alert" size={28} /></div>
      <div className="empty-title">{title}</div>
      <p className="empty-msg">{msg}</p>
      {onRetry ? <Button onClick={onRetry} icon="refresh">Try again</Button> : null}
    </div>
  );
}

export function Alert({ tone = 'error', children, title }) {
  if (!children && !title) return null;
  return (
    <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon name={tone === 'success' ? 'check' : tone === 'info' ? 'info' : 'alert'} />
      <div>
        {title ? <strong>{title}</strong> : null}
        {children ? <div>{children}</div> : null}
      </div>
    </div>
  );
}
