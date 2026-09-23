import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { RequireAuth } from '../features/auth/RequireAuth';
import { ROUTES } from '../constants/navigation';
import { CompaniesPage } from '../pages/CompaniesPage';
import { CompanyOnboardingPage } from '../pages/CompanyOnboardingPage';
import { CreateSopPage } from '../pages/CreateSopPage';
import { KnowledgePage } from '../pages/KnowledgePage';
import { LoginPage } from '../pages/LoginPage';
import { SettingsPage } from '../pages/SettingsPage';
import { SopsPage } from '../pages/SopsPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';

/** Older destinations kept available from Settings. */
const PLACEHOLDER_ROUTES = [
  { path: ROUTES.workflows, titleKey: 'nav.workflows' },
  { path: ROUTES.assistant, titleKey: 'nav.assistant' },
  { path: ROUTES.records, titleKey: 'nav.records' },
  { path: ROUTES.alerts, titleKey: 'nav.alerts' },
  { path: ROUTES.help, titleKey: 'nav.help' },
];

/** Every screen except login sits behind authentication and the labelled nav. */
function Protected({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell navigation="sidebar">{children}</AppShell>
    </RequireAuth>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path={ROUTES.login} element={<LoginPage />} />

      <Route path="/" element={<Navigate to={ROUTES.companies} replace />} />

      <Route
        path={ROUTES.companies}
        element={
          <Protected>
            <CompaniesPage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.companyCreate}
        element={
          <Protected>
            <CompanyOnboardingPage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.knowledge}
        element={
          <Protected>
            <KnowledgePage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.sopCreate}
        element={
          <Protected>
            <CreateSopPage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.sopLibrary}
        element={
          <Protected>
            <SopsPage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.settings}
        element={
          <Protected>
            <SettingsPage />
          </Protected>
        }
      />

      {PLACEHOLDER_ROUTES.map((route) => (
        <Route
          key={route.path}
          path={route.path}
          element={
            <Protected>
              <PlaceholderPage titleKey={route.titleKey} />
            </Protected>
          }
        />
      ))}

      <Route path="*" element={<Navigate to={ROUTES.companies} replace />} />
    </Routes>
  );
}
