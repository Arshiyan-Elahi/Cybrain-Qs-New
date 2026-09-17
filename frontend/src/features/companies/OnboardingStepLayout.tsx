import type { ReactNode } from 'react';
import styles from './OnboardingStepLayout.module.css';

interface OnboardingStepLayoutProps {
  title: string;
  subtitle: string;
  error?: string | null;
  children: ReactNode;
}

/** Shared panel chrome for onboarding sections after Start. */
export function OnboardingStepLayout({ title, subtitle, error, children }: OnboardingStepLayoutProps) {
  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>{title}</h2>
        <p className={styles.subtitle}>{subtitle}</p>
      </header>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <div className={styles.body}>{children}</div>
    </div>
  );
}
