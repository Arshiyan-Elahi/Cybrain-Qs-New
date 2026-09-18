import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { RequireAuth } from '../features/auth/RequireAuth';
import { ROUTES } from '../constants/navigation';
import { CompaniesPage } from '../pages/CompaniesPage';
import { CompanyOnboardingPage } from '../pages/CompanyOnboardingPage';
import { CreateSopPage } from '../pages/CreateSopPage';
import { LoginPage } from '../pages/LoginPage';
import { SettingsPage } from '../pages/SettingsPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';

/** Rail destinations that exist in the navigation but have no design yet. */
const PLACEHOLDER_ROUTES = [
  { path: ROUTES.sopLibrary, titleKey: 'placeholder.sopLibrary' },
  { path: ROUTES.workflows, titleKey: 'nav.workflows' },
  { path: ROUTES.knowledge, titleKey: 'nav.knowledge' },
  { path: ROUTES.assistant, titleKey: 'nav.assistant' },
  { path: ROUTES.records, titleKey: 'nav.records' },
  { path: ROUTES.alerts, titleKey: 'nav.alerts' },
  { path: ROUTES.help, titleKey: 'nav.help' },
];

/** Every screen except login sits behind authentication. */
function Protected({
  navigation,
  children,
}: {
  navigation: 'sidebar' | 'rail';
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <AppShell navigation={navigation}>{children}</AppShell>
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
          <Protected navigation="sidebar">
            <CompaniesPage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.companyCreate}
        element={
          <Protected navigation="rail">
            <CompanyOnboardingPage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.sopCreate}
        element={
          <Protected navigation="rail">
            <CreateSopPage />
          </Protected>
        }
      />

      <Route
        path={ROUTES.settings}
        element={
          <Protected navigation="rail">
            <SettingsPage />
          </Protected>
        }
      />

      {PLACEHOLDER_ROUTES.map((route) => (
        <Route
          key={route.path}
          path={route.path}
          element={
            <Protected navigation="rail">
              <PlaceholderPage titleKey={route.titleKey} />
            </Protected>
          }
        />
      ))}

      <Route path="*" element={<Navigate to={ROUTES.companies} replace />} />
    </Routes>
  );
}
