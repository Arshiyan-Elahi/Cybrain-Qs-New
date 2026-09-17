import type { NavItem } from '../types';

/**
 * Route paths kept in one place so links and route definitions cannot drift.
 *
 * Paths are English in every language — they are stable identifiers, not UI
 * copy, so they do not change when the user switches language.
 */
export const ROUTES = {
  login: '/login',
  companies: '/companies',
  companyCreate: '/companies/new',
  sopCreate: '/sops/new',
  sopLibrary: '/sops',
  workflows: '/workflows',
  knowledge: '/knowledge',
  assistant: '/assistant',
  records: '/records',
  alerts: '/alerts',
  settings: '/settings',
  help: '/help',
} as const;

/** The wide sidebar on the company profiles screen shows a single entry. */
export const SIDEBAR_NAV: NavItem[] = [
  { id: 'companies', labelKey: 'nav.companies', icon: 'buildingSolid', to: ROUTES.companies },
];

/**
 * The collapsed icon rail on the SOP wizard screen. The design shows seven
 * glyphs; only the first two have a labelled destination in the PDFs, the rest
 * are reserved sections and route to placeholders for now.
 */
export const RAIL_NAV: NavItem[] = [
  { id: 'companies', labelKey: 'nav.companies', icon: 'building', to: ROUTES.companies },
  { id: 'sop-create', labelKey: 'nav.sopCreate', icon: 'fileCog', to: ROUTES.sopCreate },
  { id: 'workflows', labelKey: 'nav.workflows', icon: 'workflow', to: ROUTES.workflows },
  { id: 'knowledge', labelKey: 'nav.knowledge', icon: 'book', to: ROUTES.knowledge },
  { id: 'assistant', labelKey: 'nav.assistant', icon: 'sparkles', to: ROUTES.assistant },
  { id: 'records', labelKey: 'nav.records', icon: 'clipboardPlus', to: ROUTES.records },
  { id: 'alerts', labelKey: 'nav.alerts', icon: 'siren', to: ROUTES.alerts },
];

/** Shared bottom-of-sidebar actions. */
export const SIDEBAR_FOOTER_NAV: NavItem[] = [
  { id: 'settings', labelKey: 'nav.settings', icon: 'settings', to: ROUTES.settings },
  { id: 'help', labelKey: 'nav.help', icon: 'lifeBuoy', to: ROUTES.help },
  { id: 'logout', labelKey: 'nav.logout', icon: 'logOut', to: ROUTES.login },
];
