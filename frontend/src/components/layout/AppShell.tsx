import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { IconRail } from './IconRail';
import styles from './AppShell.module.css';

interface AppShellProps {
  /**
   * `sidebar` is the wide navigation used by the company screens;
   * `rail` is the collapsed icon rail used by the SOP wizard.
   */
  navigation: 'sidebar' | 'rail';
  children: ReactNode;
}

/** Chrome shared by every screen: navigation on the left, scrolling content. */
export function AppShell({ navigation, children }: AppShellProps) {
  return (
    <div className={styles.shell}>
      {navigation === 'sidebar' ? <Sidebar /> : <IconRail />}
      <main className={styles.main}>{children}</main>
    </div>
  );
}
