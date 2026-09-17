import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../common/Icon';
import { SIDEBAR_FOOTER_NAV } from '../../constants/navigation';
import { useAuth } from '../../features/auth/useAuth';
import styles from './SidebarFooter.module.css';

interface SidebarFooterProps {
  /** `rail` hides labels and centres the glyphs for the collapsed rail. */
  variant?: 'full' | 'rail';
}

/**
 * Settings / Help / Log out. Undesigned destinations use honest placeholders.
 */
export function SidebarFooter({ variant = 'full' }: SidebarFooterProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const isRail = variant === 'rail';

  return (
    <nav className={isRail ? `${styles.footer} ${styles.rail}` : styles.footer}>
      {SIDEBAR_FOOTER_NAV.map((item) => {
        const label = t(item.labelKey);
        return (
          <button
            key={item.id}
            type="button"
            className={styles.item}
            title={isRail ? label : undefined}
            aria-label={isRail ? label : undefined}
            onClick={() => {
              if (item.id === 'logout') signOut();
              else navigate(item.to);
            }}
          >
            <Icon name={item.icon} size={20} strokeWidth={1.9} />
            {!isRail && <span>{label}</span>}
          </button>
        );
      })}
    </nav>
  );
}
