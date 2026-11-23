import { Link } from "react-router-dom";
export default function NotFoundPage() {
  return <div className="page empty-state"><h1>Page not found</h1><p>The page you requested does not exist.</p><Link className="primary-button" to="/">Go to store</Link></div>;
}