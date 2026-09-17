import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  /** Percentage 0–100. */
  value: number;
  /** `lg` = 11px track (headline figures), `sm` = 5px track (metric rows). */
  size?: 'lg' | 'sm';
  label?: string;
}

/** Rounded progress track used by the AI analysis summary. */
export function ProgressBar({ value, size = 'sm', label }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div
      className={`${styles.track} ${styles[size]}`}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className={styles.fill} style={{ width: `${clamped}%` }} />
    </div>
  );
}
