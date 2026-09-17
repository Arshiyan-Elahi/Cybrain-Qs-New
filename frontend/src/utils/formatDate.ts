/** BCP 47 locale used for formatting per UI language. */
const LOCALES: Record<string, string> = {
  de: 'de-DE',
  // Day-first, matching the European context the product targets.
  en: 'en-GB',
};

/**
 * Format an ISO `YYYY-MM-DD` date for display in the active language.
 * German renders as `15.05.2025`, exactly as printed in the design.
 * Returns the input unchanged if it is not a valid date.
 */
export function formatDate(isoDate: string, language: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return isoDate;

  const locale = LOCALES[language.split('-')[0]] ?? LOCALES.en;
  return new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
}
