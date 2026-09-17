import styles from './Wordmark.module.css';

interface WordmarkProps {
  /**
   * `inline` renders "Cybrain QS" on one line (wide sidebar);
   * `stacked` renders it over two centred lines (collapsed icon rail).
   */
  variant?: 'inline' | 'stacked';
}

export function Wordmark({ variant = 'inline' }: WordmarkProps) {
  if (variant === 'stacked') {
    return (
      <div className={`${styles.wordmark} ${styles.stacked}`}>
        <span>Cybrain</span>
        <span>QS</span>
      </div>
    );
  }

  return <div className={styles.wordmark}>Cybrain QS</div>;
}
