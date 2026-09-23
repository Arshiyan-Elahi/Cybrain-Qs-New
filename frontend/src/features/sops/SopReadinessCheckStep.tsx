import { useTranslation } from 'react-i18next';
import { TextField } from '../../components/forms/TextField';
import { Icon } from '../../components/common/Icon';
import { WIZARD_STEPS } from '../../constants/wizard';
import type { SopProject } from '../../types';
import { requiredGapQuestions, gapNeedLabelKey } from './gapQuestions';
import styles from './SopReadinessCheckStep.module.css';

interface SopReadinessCheckStepProps {
  project: SopProject | null;
  gapAnswers: Record<string, string>;
  onGapAnswerChange: (key: string, value: string) => void;
}

/** Step 3 — ready vs needs information, with plain-language gap questions. */
export function SopReadinessCheckStep({
  project,
  gapAnswers,
  onGapAnswerChange,
}: SopReadinessCheckStepProps) {
  const { t } = useTranslation();
  const step = WIZARD_STEPS[2];
  const blueprint = project?.blueprint;
  const sections = blueprint?.sections ?? [];
  const ready = sections.filter((section) => section.generationStatus === 'grounded');
  const needsInfo = sections.filter((section) => section.generationStatus !== 'grounded');
  const questions = requiredGapQuestions(sections);

  return (
    <div className={styles.panel}>
      <h2 className={styles.title}>
        {step.ordinal}. {t(step.labelKey)}
      </h2>
      <p className={styles.hero}>{t('sop.guided.step3.hero')}</p>
      <p className={styles.lead}>{t('sop.guided.step3.lead')}</p>

      {!blueprint && <p className={styles.note}>{t('sop.guided.step3.noPlan')}</p>}

      {blueprint && (
        <div className={styles.columns}>
          <section className={styles.listCard} aria-labelledby="ready-heading">
            <h3 id="ready-heading">{t('sop.guided.step3.readyHeading')}</h3>
            {ready.length === 0 ? (
              <p className={styles.empty}>{t('sop.guided.step3.noneReady')}</p>
            ) : (
              <ul className={styles.list}>
                {ready.map((section) => (
                  <li key={section.sectionKey} className={styles.readyItem}>
                    <Icon name="check" size={16} strokeWidth={2.2} />
                    <span>{section.heading}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className={styles.listCard} aria-labelledby="needs-heading">
            <h3 id="needs-heading">{t('sop.guided.step3.needsHeading')}</h3>
            {needsInfo.length === 0 ? (
              <p className={styles.empty}>{t('sop.guided.step3.noneNeeds')}</p>
            ) : (
              <ul className={styles.list}>
                {needsInfo.map((section) => {
                  const requiredGaps = section.gaps.filter((gap) => gap.severity === 'required');
                  const label = requiredGaps.length > 0
                    ? requiredGaps.map((gap) => t(gapNeedLabelKey(gap), { heading: section.heading })).join('; ')
                    : t(`sop.blueprint.status.${section.generationStatus}`);
                  return (
                    <li key={section.sectionKey} className={styles.needsItem}>
                      <span className={styles.bang} aria-hidden>!</span>
                      <span>
                        <strong>{section.heading}</strong>
                        <span className={styles.gapReason}>{label}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      )}

      {questions.length > 0 && (
        <section className={styles.questions} aria-labelledby="gap-questions-heading">
          <h3 id="gap-questions-heading">{t('sop.guided.step3.questionsHeading')}</h3>
          <p className={styles.note}>{t('sop.guided.step3.questionsLead')}</p>
          <ul className={styles.questionList}>
            {questions.map((question) => (
              <li key={question.key} className={styles.question}>
                <p className={styles.questionLabel}>
                  {t(question.questionKey, question.questionParams)}
                </p>
                <p className={styles.questionMeta}>
                  {t('sop.guided.step3.aboutSection', { heading: question.sectionHeading })}
                </p>
                <TextField
                  value={gapAnswers[question.key] ?? ''}
                  onChange={(next) => onGapAnswerChange(question.key, next)}
                  placeholder={t('sop.guided.step3.answerPlaceholder')}
                  aria-label={t(question.questionKey, question.questionParams)}
                />
                <p className={styles.disclaimer}>{t('sop.guided.step3.answerDisclaimer')}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {blueprint && blueprint.summary.blocked > 0 && (
        <p className={styles.blockedNote} role="status">
          {t('sop.guided.step3.blockedNote', { count: blueprint.summary.blocked })}
        </p>
      )}
    </div>
  );
}
