import type { ReactNode } from 'react';
import { Icon } from './Icon';
import styles from './InfoPanel.module.css';

interface InfoPanelProps {
  title: string;
  children: ReactNode;
}

/** Lavender explainer callout at the bottom of the Unternehmensprofile page. */
export function InfoPanel({ title, children }: InfoPanelProps) {
  return (
    <aside className={styles.panel}>
      <Icon name="alertCircle" size={54} strokeWidth={2.6} className={styles.icon} />
      <div className={styles.body}>
        <h2 className={styles.title}>{title}</h2>
        <p className={styles.text}>{children}</p>
      </div>
    </aside>
  );
}
