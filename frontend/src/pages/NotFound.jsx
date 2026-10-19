import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="no-access">
      <h1>Page not found</h1>
      <p className="muted">The page you are looking for does not exist.</p>
      <Link to="/" className="btn btn-primary btn-md">Go to home</Link>
    </div>
  );
}
