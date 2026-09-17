import type { CSSProperties } from 'react';

/**
 * Every glyph that appears in the design PDFs. Icons are drawn on a 24x24
 * grid and inherit `currentColor` so a single component covers the purple,
 * white-on-purple and duotone treatments used across the screens.
 */
export type IconName =
  | 'building'
  | 'buildingSolid'
  | 'plus'
  | 'chevronRight'
  | 'chevronLeft'
  | 'chevronDown'
  | 'search'
  | 'settings'
  | 'lifeBuoy'
  | 'logOut'
  | 'alertCircle'
  | 'fileCog'
  | 'workflow'
  | 'book'
  | 'sparkles'
  | 'clipboardPlus'
  | 'siren'
  | 'arrowLeft'
  | 'arrowRight'
  | 'checkCircle'
  | 'fileText'
  | 'check'
  /* Client onboarding — "Was hast du?" choices */
  | 'wordTemplate'
  | 'documentsStack'
  | 'blankPage'
  /* Client onboarding — AI analysis metrics */
  | 'docStructure'
  | 'writingStyle'
  | 'terminology'
  | 'regulatoryScan'
  | 'workflowExtract'
  | 'metadataExtract';

interface IconProps {
  name: IconName;
  size?: number;
  /** Stroke width for the outline glyphs. */
  strokeWidth?: number;
  className?: string;
  style?: CSSProperties;
}

const STROKE_DEFAULTS = {
  fill: 'none',
  stroke: 'currentColor',
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

export function Icon({ name, size = 24, strokeWidth = 2, className, style }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    className,
    style,
    'aria-hidden': true,
    focusable: false,
  } as const;

  const stroke = { ...STROKE_DEFAULTS, strokeWidth };

  switch (name) {
    /* Duotone building used on the company tiles: a solid tower in the
     * current colour flanked by lighter wings. */
    case 'buildingSolid':
      return (
        <svg {...common}>
          {/* Side wings sit behind the tower in a mid purple on both the
              lavender and the solid purple tile treatments. */}
          <g fill="var(--c-brand-tile-strong, #b9a9e6)">
            <path d="M4.9 7.6h4V19h-4a1 1 0 0 1-1-1V8.6a1 1 0 0 1 1-1Z" />
            <path d="M15.1 7.6h4a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1h-4V7.6Z" />
          </g>
          <g fill="var(--icon-cutout, #f4f0fd)" opacity="0.85">
            <rect x="5.2" y="9.7" width="2.5" height="1.2" rx="0.6" />
            <rect x="5.2" y="12.1" width="2.5" height="1.2" rx="0.6" />
            <rect x="5.2" y="14.5" width="2.5" height="1.2" rx="0.6" />
            <rect x="16.3" y="9.7" width="2.5" height="1.2" rx="0.6" />
            <rect x="16.3" y="12.1" width="2.5" height="1.2" rx="0.6" />
            <rect x="16.3" y="14.5" width="2.5" height="1.2" rx="0.6" />
          </g>

          {/* Tower and base bar take the icon colour. */}
          <path
            d="M9.4 4.2h5.2c.75 0 1.35.6 1.35 1.35V19H8.05V5.55c0-.75.6-1.35 1.35-1.35Z"
            fill="currentColor"
          />
          <rect x="3.1" y="18.5" width="17.8" height="1.9" rx="0.95" fill="currentColor" />

          {/* Windows are punched out in the tile background colour. */}
          <g fill="var(--icon-cutout, #e4dff4)">
            <rect x="9.9" y="6.5" width="4.2" height="1.35" rx="0.67" />
            <rect x="9.9" y="9" width="4.2" height="1.35" rx="0.67" />
            <rect x="9.9" y="11.5" width="4.2" height="1.35" rx="0.67" />
            <rect x="9.9" y="14" width="4.2" height="1.35" rx="0.67" />
            <rect x="11.35" y="16.1" width="1.3" height="2.4" rx="0.65" />
          </g>
        </svg>
      );

    /* Outline building used in the icon rail. */
    case 'building':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M8 20V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V20" />
            <path d="M8 9H5.5A1.5 1.5 0 0 0 4 10.5V20" opacity="0.45" />
            <path d="M16 9h2.5A1.5 1.5 0 0 1 20 10.5V20" opacity="0.45" />
            <path d="M11 8h2M11 11h2M11 14h2" />
            <path d="M3 20h18" />
          </g>
        </svg>
      );

    case 'plus':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M12 5v14M5 12h14" />
          </g>
        </svg>
      );

    case 'chevronRight':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="m9 6 6 6-6 6" />
          </g>
        </svg>
      );

    case 'chevronLeft':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="m15 6-6 6 6 6" />
          </g>
        </svg>
      );

    case 'chevronDown':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="m6 9 6 6 6-6" />
          </g>
        </svg>
      );

    case 'search':
      return (
        <svg {...common}>
          <g {...stroke}>
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.6-3.6" />
          </g>
        </svg>
      );

    case 'settings':
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            d="M10.3 2h3.4l.4 2.1c.5.17.98.4 1.42.7l2-.78 1.7 2.96-1.6 1.4c.5.4.08.8.08 1.22s-.03.82-.08 1.22l1.6 1.4-1.7 2.96-2-.78c-.44.3-.92.53-1.42.7L13.7 22h-3.4l-.4-2.1a6.3 6.3 0 0 1-1.42-.7l-2 .78-1.7-2.96 1.6-1.4A6.6 6.6 0 0 1 6.3 12c0-.42.03-.82.08-1.22l-1.6-1.4 1.7-2.96 2 .78c.44-.3.92-.53 1.42-.7L10.3 2Zm1.7 6.6a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8Z"
          />
        </svg>
      );

    case 'lifeBuoy':
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            fillRule="evenodd"
            d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 6.4a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2Z"
            clipRule="evenodd"
          />
          <g stroke="var(--c-surface-soft, #f9f9fd)" strokeWidth="1.8" strokeLinecap="round">
            <path d="m5.6 5.6 3.9 3.9M14.5 14.5l3.9 3.9M18.4 5.6l-3.9 3.9M9.5 14.5l-3.9 3.9" />
          </g>
        </svg>
      );

    case 'logOut':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M14 4.6a8 8 0 1 0 0 14.8" />
            <path d="M13 12h9M18.5 8.5 22 12l-3.5 3.5" />
          </g>
        </svg>
      );

    case 'alertCircle':
      return (
        <svg {...common}>
          <g {...stroke}>
            <circle cx="12" cy="12" r="9.2" />
            <path d="M12 7.2v6.1" />
          </g>
          <circle cx="12" cy="16.6" r="1.15" fill="currentColor" />
        </svg>
      );

    case 'fileCog':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M13.4 3H7a1.8 1.8 0 0 0-1.8 1.8v14.4A1.8 1.8 0 0 0 7 21h3.1" />
            <path d="M13.4 3 19 8.6V11" />
            <path d="M13.2 3.3v4.4a1 1 0 0 0 1 1h4.4" />
            <circle cx="16.6" cy="17.1" r="2.5" />
            <path d="M16.6 13.3v1M16.6 20.9v1M20.4 17.1h-1M13.8 17.1h-1M19.3 14.4l-.7.7M14.6 19.1l-.7.7M19.3 19.8l-.7-.7M14.6 15.1l-.7-.7" />
          </g>
        </svg>
      );

    case 'workflow':
      return (
        <svg {...common}>
          <g {...stroke}>
            <circle cx="9" cy="6.5" r="2.5" />
            <circle cx="9" cy="17.5" r="2.5" />
            <circle cx="18" cy="14" r="2.5" />
            <path d="M9 9v6" />
            <path d="M9.6 15.6 15.6 13" />
          </g>
        </svg>
      );

    case 'book':
      return (
        <svg {...common}>
          <g {...stroke}>
            <rect x="5" y="3.5" width="14" height="17" rx="2.2" />
            <path d="M5 16.5h14" />
            <path d="M8.5 7.5h7M8.5 11h4.5" />
          </g>
        </svg>
      );

    case 'sparkles':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M10.4 3.6 12 8.2l4.6 1.6-4.6 1.6-1.6 4.6-1.6-4.6L4.2 9.8l4.6-1.6 1.6-4.6Z" />
            <path d="M17.6 14.4l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z" />
            <path d="M18.2 3.4v2.4M17 4.6h2.4" />
          </g>
        </svg>
      );

    case 'clipboardPlus':
      return (
        <svg {...common}>
          <g {...stroke}>
            <rect x="4.6" y="5" width="14.8" height="16" rx="2.2" />
            <path d="M9.2 3h5.6a1 1 0 0 1 1 1v1.8a1 1 0 0 1-1 1H9.2a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
            <path d="M8.4 11.5h7.2M8.4 15h4.2" />
            <path d="M16.6 14.4v4.6M14.3 16.7h4.6" />
          </g>
        </svg>
      );

    case 'siren':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M6.5 20v-5a5.5 5.5 0 0 1 11 0v5" />
            <path d="M4.6 20h14.8" />
            <path d="M12 2.4v2.1M5.6 5l1.5 1.5M18.4 5l-1.5 1.5" />
            <path d="m12.6 11.4-2.2 3h3.2l-2.2 3" />
          </g>
        </svg>
      );

    case 'arrowLeft':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M20 12H4M10 6l-6 6 6 6" />
          </g>
        </svg>
      );

    case 'arrowRight':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M4 12h16M14 6l6 6-6 6" />
          </g>
        </svg>
      );

    case 'checkCircle':
      return (
        <svg {...common}>
          <g {...stroke}>
            <circle cx="12" cy="12" r="9" />
            <path d="m8.2 12.2 2.6 2.6 5-5.4" />
          </g>
        </svg>
      );

    case 'fileText':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="M13.6 3H7a1.8 1.8 0 0 0-1.8 1.8v14.4A1.8 1.8 0 0 0 7 21h10a1.8 1.8 0 0 0 1.8-1.8V8.2L13.6 3Z" />
            <path d="M13.4 3.3v4.4a1 1 0 0 0 1 1h4.4" />
            <path d="M8.6 13h6.8M8.6 16.4h4.4" />
          </g>
        </svg>
      );

    case 'check':
      return (
        <svg {...common}>
          <g {...stroke}>
            <path d="m5 12.8 4.6 4.4L19 6.6" />
          </g>
        </svg>
      );

    /* ---- Client onboarding: "Was möchtest du mitbringen?" ---- */

    /* Word-style template: slanted document body with a white W, plus a
       separate spine bar on the right. */
    case 'wordTemplate':
      return (
        <svg {...common}>
          <path d="M3.4 5.1 14.1 3.1a.7.7 0 0 1 .85.69v16.42a.7.7 0 0 1-.85.69L3.4 19.5a.9.9 0 0 1-.73-.88V5.98a.9.9 0 0 1 .73-.88Z" fill="currentColor" />
          <path d="M16.6 5.4h3.1a.85.85 0 0 1 .85.85v11.5a.85.85 0 0 1-.85.85h-3.1V5.4Z" fill="currentColor" opacity="0.72" />
          <path
            d="m5.1 8.9 1.35 4.55L7.9 8.9h1.5l1.45 4.55L12.2 8.9h1.55l-2.3 6.9h-1.6L8.62 11.9 7.4 15.8H5.8L3.55 8.9H5.1Z"
            fill="var(--icon-cutout, #ffffff)"
          />
        </svg>
      );

    /* Two stacked documents, the front one filled with rule lines. */
    case 'documentsStack':
      return (
        <svg {...common}>
          <path
            d="M11.4 2.6h3.9L20 7.3v9.1a1.6 1.6 0 0 1-1.6 1.6h-1V9.2a1.6 1.6 0 0 0-.47-1.13l-4.5-4.5a1.6 1.6 0 0 0-1.03-.47Z"
            fill="currentColor"
            opacity="0.55"
          />
          <path
            d="M5.6 5.6h6.1l4.7 4.7v9.5a1.6 1.6 0 0 1-1.6 1.6H5.6A1.6 1.6 0 0 1 4 19.8V7.2a1.6 1.6 0 0 1 1.6-1.6Z"
            fill="currentColor"
          />
          <g fill="var(--icon-cutout, #ffffff)">
            <rect x="6.9" y="13.4" width="6.4" height="1.5" rx="0.75" />
            <rect x="6.9" y="16.5" width="4.4" height="1.5" rx="0.75" />
          </g>
        </svg>
      );

    /* Empty page with a folded corner. */
    case 'blankPage':
      return (
        <svg {...common}>
          <g {...stroke} strokeWidth={2.1}>
            <path d="M13.6 3H7.4A1.9 1.9 0 0 0 5.5 4.9v14.2A1.9 1.9 0 0 0 7.4 21h9.2a1.9 1.9 0 0 0 1.9-1.9V7.7L13.6 3Z" />
            <path d="M13.4 3.3v3.6a1.4 1.4 0 0 0 1.4 1.4h3.4" />
          </g>
        </svg>
      );

    /* ---- Client onboarding: AI analysis metrics ---- */

    case 'docStructure':
      return (
        <svg {...common}>
          <g {...stroke} strokeWidth={1.7}>
            <path d="M13.6 3H7.4A1.9 1.9 0 0 0 5.5 4.9v14.2A1.9 1.9 0 0 0 7.4 21h9.2a1.9 1.9 0 0 0 1.9-1.9V7.7L13.6 3Z" />
            <path d="M13.4 3.3v3.6a1.4 1.4 0 0 0 1.4 1.4h3.4" />
            <path d="M9 12.6h6M9 16.1h3.6" />
          </g>
        </svg>
      );

    case 'writingStyle':
      return (
        <svg {...common}>
          <g {...stroke} strokeWidth={1.7}>
            <path d="M11.4 4.4H6.2A1.8 1.8 0 0 0 4.4 6.2v11.6a1.8 1.8 0 0 0 1.8 1.8h11.6a1.8 1.8 0 0 0 1.8-1.8v-5.2" />
            <path d="M17.4 3.9a1.9 1.9 0 0 1 2.7 2.7l-7.5 7.5-3.4.7.7-3.4 7.5-7.5Z" />
          </g>
        </svg>
      );

    case 'terminology':
      return (
        <svg {...common}>
          <g {...stroke} strokeWidth={1.7}>
            <path d="M7.8 4.4A8.6 8.6 0 0 0 4.4 9M16.2 4.4A8.6 8.6 0 0 1 19.6 9M7.8 19.6A8.6 8.6 0 0 1 4.4 15M16.2 19.6a8.6 8.6 0 0 0 3.4-4.6" />
            <circle cx="12" cy="12" r="4.1" />
          </g>
          <circle cx="12" cy="12" r="2" fill="currentColor" />
        </svg>
      );

    case 'regulatoryScan':
      return (
        <svg {...common}>
          <g {...stroke} strokeWidth={1.7}>
            <path d="M20.2 13.2V6.1a1.5 1.5 0 0 0-1.5-1.5H7.9a1.5 1.5 0 0 0-1.5 1.5v7.1a1.5 1.5 0 0 0 1.5 1.5h4.3" />
            <path d="M10 11.6V9.3M13 11.6V7.6M16.2 11.6v-1.5" />
            <path d="M3.8 8.2v9.3a1.5 1.5 0 0 0 1.5 1.5h4.4" />
            <circle cx="16.4" cy="17.2" r="3" />
            <path d="m18.7 19.5 1.8 1.8" />
          </g>
        </svg>
      );

    case 'workflowExtract':
      return (
        <svg {...common}>
          <g {...stroke} strokeWidth={1.7}>
            <path d="M5 11.2a7 7 0 0 1 11.7-4.5" />
            <path d="M16.9 3.6v3.4h-3.4" />
            <path d="M10.6 19.6A7 7 0 0 1 5.1 15" />
            <path d="M4.6 19v-3.4H8" />
            <circle cx="16.3" cy="16.3" r="2.4" />
            <path d="M16.3 12.6v1M16.3 20v1M20 16.3h-1M13.6 16.3h-1M18.9 13.7l-.7.7M14.4 18.2l-.7.7M18.9 18.9l-.7-.7M14.4 14.4l-.7-.7" />
          </g>
        </svg>
      );

    case 'metadataExtract':
      return (
        <svg {...common}>
          <g {...stroke} strokeWidth={1.7}>
            <path d="M12 7.1 15.9 9.3v4.4L12 15.9l-3.9-2.2V9.3L12 7.1Z" />
            <path d="M12 11.5v4.4M12 11.5 8.1 9.3M12 11.5l3.9-2.2" />
            <path d="M4.6 9.6A7.7 7.7 0 0 1 9.9 3.7" />
            <path d="M3.3 6.4 4.6 9.9 8 8.6" />
            <path d="M19.4 14.4a7.7 7.7 0 0 1-5.3 5.9" />
            <path d="M20.7 17.6 19.4 14.1 16 15.4" />
          </g>
        </svg>
      );

    default:
      return null;
  }
}
