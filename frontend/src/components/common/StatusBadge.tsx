import styles from './StatusBadge.module.css';

interface StatusBadgeProps {
  children: string;
}

/** Pill used for the "Regulatorische Anforderungen" list. */
export function StatusBadge({ children }: StatusBadgeProps) {
  return <span className={styles.badge}>{children}</span>;
}
