import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Icon } from '../common/Icon';
import { SIDEBAR_NAV } from '../../constants/navigation';
import { SidebarFooter } from './SidebarFooter';
import { Wordmark } from './Wordmark';
import styles from './Sidebar.module.css';

/** Labelled navigation for the everyday product tasks. */
export function Sidebar() {
  const { t } = useTranslation();

  return (
    <aside className={styles.sidebar}>
      <Wordmark />

      <nav className={styles.nav} aria-label={t('ux.navLabel')}>
        {SIDEBAR_NAV.map((item) => (
          <NavLink
            key={item.id}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              isActive ? `${styles.navItem} ${styles.navItemActive}` : styles.navItem
            }
          >
            <Icon name={item.icon} size={22} />
            <span>{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.spacer} />
      <SidebarFooter />
    </aside>
  );
}
