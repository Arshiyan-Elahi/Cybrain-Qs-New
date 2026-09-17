import type { ReactNode } from 'react';
import styles from './FieldCard.module.css';

interface FieldCardProps {
  title: string;
  /** Question line under the title, e.g. "Wie soll die SOP benannt werden?". */
  hint?: string;
  /** The design uses 20px padding on the left column and 32px on the right. */
  density?: 'tight' | 'roomy';
  children: ReactNode;
}

/** Bordered panel that groups one field of the wizard. */
export function FieldCard({ title, hint, density = 'tight', children }: FieldCardProps) {
  return (
    <section className={density === 'roomy' ? `${styles.card} ${styles.roomy}` : styles.card}>
      <h3 className={styles.title}>{title}</h3>
      {hint && <p className={styles.hint}>{hint}</p>}
      <div className={styles.body}>{children}</div>
    </section>
  );
}
