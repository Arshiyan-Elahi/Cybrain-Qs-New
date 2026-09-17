import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Icon } from '../common/Icon';
import { RAIL_NAV } from '../../constants/navigation';
import { SidebarFooter } from './SidebarFooter';
import { Wordmark } from './Wordmark';
import styles from './IconRail.module.css';

/** Collapsed icon rail used by the SOP wizard screens. */
export function IconRail() {
  const { t } = useTranslation();

  return (
    <aside className={styles.rail}>
      <Wordmark variant="stacked" />

      <nav className={styles.nav}>
        {RAIL_NAV.map((item) => (
          <NavLink
            key={item.id}
            to={item.to}
            title={t(item.labelKey)}
            aria-label={t(item.labelKey)}
            className={({ isActive }) =>
              isActive ? `${styles.item} ${styles.itemActive}` : styles.item
            }
          >
            <Icon name={item.icon} size={item.icon === 'building' ? 22 : 20} strokeWidth={1.9} />
          </NavLink>
        ))}
      </nav>

      <div className={styles.spacer} />
      <SidebarFooter variant="rail" />
    </aside>
  );
}
