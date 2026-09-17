import { Fragment } from 'react';
import { useTranslation } from 'react-i18next';
import type { WizardStep } from '../../types';
import styles from './WizardStepper.module.css';

interface WizardStepperProps {
  steps: WizardStep[];
  /** Zero-based index of the step currently being shown. */
  activeIndex: number;
  onStepSelect?: (index: number) => void;
  /** Draw a short rule between consecutive steps (client onboarding design). */
  connected?: boolean;
  /** Translation key for the nav's accessible name. */
  ariaLabelKey?: string;
}

/** Wizard progress header. Used by both the SOP and client onboarding wizards. */
export function WizardStepper({
  steps,
  activeIndex,
  onStepSelect,
  connected = false,
  ariaLabelKey = 'sop.wizard.stepperLabel',
}: WizardStepperProps) {
  const { t } = useTranslation();

  return (
    <nav className={styles.stepper} aria-label={t(ariaLabelKey)}>
      <ol className={connected ? `${styles.list} ${styles.listConnected}` : styles.list}>
        {steps.map((step, index) => {
          const isActive = index === activeIndex;
          const showSeparator = connected && index > 0;

          return (
            <Fragment key={step.ordinal}>
              {showSeparator &&
                (step.truncatedBefore ? (
                  <li className={styles.ellipsis} aria-hidden>
                    <span />
                    <span />
                    <span />
                  </li>
                ) : (
                  <li className={styles.connector} aria-hidden />
                ))}

              <li className={styles.item}>
                <button
                  type="button"
                  className={isActive ? `${styles.step} ${styles.stepActive}` : styles.step}
                  aria-current={isActive ? 'step' : undefined}
                  onClick={() => onStepSelect?.(index)}
                >
                  <span className={styles.circle}>{step.ordinal}</span>
                  <span className={styles.label}>{t(step.labelKey)}</span>
                </button>
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
