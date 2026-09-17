import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ROUTES } from '../../constants/navigation';
import { useAuth } from './useAuth';

/** Sends unauthenticated visitors to the login screen, preserving where they were going. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Render nothing while the stored token is being verified, so a valid
  // session never flashes the login screen on reload.
  if (loading) return null;

  if (!user) {
    return <Navigate to={ROUTES.login} state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}
