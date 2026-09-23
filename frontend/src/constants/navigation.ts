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

/**
 * Everyday navigation. Longer product areas stay reachable from Settings.
 * `end` keeps SOPs from staying active while Create SOP is open.
 */
export const SIDEBAR_NAV: NavItem[] = [
  { id: 'companies', labelKey: 'nav.companies', icon: 'building', to: ROUTES.companies, end: true },
  { id: 'knowledge', labelKey: 'nav.companyKnowledge', icon: 'book', to: ROUTES.knowledge, end: true },
  { id: 'sop-create', labelKey: 'nav.sopCreate', icon: 'fileCog', to: ROUTES.sopCreate, end: true },
  { id: 'sops', labelKey: 'nav.sops', icon: 'fileText', to: ROUTES.sopLibrary, end: true },
  { id: 'settings', labelKey: 'nav.settings', icon: 'settings', to: ROUTES.settings, end: true },
];

/**
 * Previous icon-rail destinations. Kept so those routes remain reachable
 * from Settings rather than the primary navigation.
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

/** Areas that are not part of the everyday path. Linked from Settings. */
export const ADVANCED_NAV: NavItem[] = [
  { id: 'workflows', labelKey: 'nav.workflows', icon: 'workflow', to: ROUTES.workflows },
  { id: 'assistant', labelKey: 'nav.assistant', icon: 'sparkles', to: ROUTES.assistant },
  { id: 'records', labelKey: 'nav.records', icon: 'clipboardPlus', to: ROUTES.records },
  { id: 'alerts', labelKey: 'nav.alerts', icon: 'siren', to: ROUTES.alerts },
  { id: 'help', labelKey: 'nav.help', icon: 'lifeBuoy', to: ROUTES.help },
];

/** Shared bottom-of-sidebar actions. Settings lives in the primary nav. */
export const SIDEBAR_FOOTER_NAV: NavItem[] = [
  { id: 'help', labelKey: 'nav.help', icon: 'lifeBuoy', to: ROUTES.help },
  { id: 'logout', labelKey: 'nav.logout', icon: 'logOut', to: ROUTES.login },
];
