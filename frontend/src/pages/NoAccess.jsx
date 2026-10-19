import { Link } from 'react-router-dom';
import Icon from '../components/Icon';

export default function NoAccess() {
  return (
    <div className="no-access">
      <div className="empty-icon error"><Icon name="quality" size={32} /></div>
      <h1>No access</h1>
      <p className="muted">Your role does not have permission to view this page. Contact an administrator if you need access.</p>
      <Link to="/" className="btn btn-primary btn-md">Go to home</Link>
    </div>
  );
}
