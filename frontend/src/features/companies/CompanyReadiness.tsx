import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { ProgressBar } from '../../components/common/ProgressBar';
import { ROUTES } from '../../constants/navigation';
import { getCompanyStats } from '../../services/companies';
import { listAllKnowledgeObjects } from '../../services/knowledge';
import type { CompanyStats, KnowledgeObject } from '../../types';
import {
  deriveCompanyReadiness,
  type CompanyReadinessModel,
} from './readinessModel';
import styles from './CompanyReadiness.module.css';

type Placement = 'company' | 'knowledge' | 'sops';

interface CompanyReadinessProps {
  companyId: string;
  companyName?: string;
  /** Where the summary is shown, so the next action is not repeated. */
  placement?: Placement;
  /** Drop the outer card when already inside the company profile card. */
  embedded?: boolean;
}

export function CompanyReadiness({
  companyId,
  companyName,
  placement = 'company',
  embedded = false,
}: CompanyReadinessProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [stats, setStats] = useState<CompanyStats | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      getCompanyStats(companyId),
      listAllKnowledgeObjects(companyId),
    ])
      .then(([nextStats, items]) => {
        if (cancelled) return;
        setStats(nextStats);
        setKnowledge(items);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : t('common.requestFailed'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, reloadKey, t]);

  const model: CompanyReadinessModel | null = loading || error
    ? null
    : deriveCompanyReadiness(stats, knowledge);

  const action = model ? nextAction(placement, model.current, companyId) : null;

  return (
    <section className={embedded ? styles.embedded : styles.card} aria-label={t('ux.readiness.label')}>
      <div className={styles.heading}>
        <div>
          <h3 className={styles.title}>{t('ux.readiness.title')}</h3>
          <p className={styles.lead}>
            {companyName
              ? t('ux.readiness.leadNamed', { name: companyName })
              : t('ux.readiness.lead')}
          </p>
        </div>
        {model && (
          <p className={styles.percent}>
            {t('ux.readiness.percent', { value: model.progress })}
          </p>
        )}
      </div>

      {loading && <p className={styles.note}>{t('common.loading')}</p>}
      {error && (
        <p className={styles.error} role="alert">
          {t('common.loadFailed', { message: error })}{' '}
          <button type="button" className={styles.retry} onClick={() => setReloadKey((value) => value + 1)}>
            {t('common.retry')}
          </button>
        </p>
      )}

      {model && (
        <>
          <ProgressBar value={model.progress} size="lg" label={t('ux.readiness.label')} />
          <ol className={styles.steps}>
            {model.steps.map((step, index) => (
              <li key={step.id} className={`${styles.step} ${styles[step.state]}`}>
                <span className={styles.stepIndex}>{index + 1}</span>
                <span className={styles.stepBody}>
                  <span className={styles.stepName}>{t(`ux.readiness.steps.${step.id}`)}</span>
                  <span className={styles.stepState}>{stepStateLabel(t, step, model)}</span>
                </span>
              </li>
            ))}
          </ol>
          <p className={styles.summary}>{summaryText(t, model)}</p>
          {action && (
            <div className={styles.actions}>
              <Button
                onClick={() => {
                  if (action.kind === 'scroll') {
                    document.getElementById('company-documents')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    return;
                  }
                  navigate(action.to);
                }}
              >
                {t(action.labelKey)}
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function stepStateLabel(
  t: (key: string) => string,
  step: { id: string; state: string },
  model: CompanyReadinessModel,
): string {
  const waitingOnUser = step.state === 'current'
    && !(step.id === 'documents' && model.documents > 0);
  return t(waitingOnUser ? 'ux.readiness.state.todo' : `ux.readiness.state.${step.state}`);
}

function summaryText(
  t: (key: string, options?: Record<string, unknown>) => string,
  model: CompanyReadinessModel,
): string {
  if (model.current === 'documents') {
    return model.documents === 0
      ? t('ux.readiness.summary.upload')
      : t('ux.readiness.summary.reading');
  }
  if (model.current === 'review') {
    return model.proposed > 0
      ? t('ux.readiness.summary.review', { count: model.proposed })
      : t('ux.readiness.summary.find');
  }
  if (model.current === 'ready') return t('ux.readiness.summary.confirmOne');
  return t('ux.readiness.summary.ready', { count: model.verified });
}

function nextAction(
  placement: Placement,
  current: CompanyReadinessModel['current'],
  companyId: string,
): { kind: 'navigate' | 'scroll'; to: string; labelKey: string } | null {
  const knowledgeTo = `${ROUTES.knowledge}?company=${companyId}`;
  const companiesTo = `${ROUTES.companies}?company=${companyId}`;
  const createTo = `${ROUTES.sopCreate}?company=${companyId}`;

  if (current === 'complete') {
    if (placement === 'sops') return null;
    return { kind: 'navigate', to: createTo, labelKey: 'ux.readiness.action.create' };
  }
  if (current === 'documents') {
    if (placement === 'company') {
      return { kind: 'scroll', to: '', labelKey: 'ux.readiness.action.documents' };
    }
    return { kind: 'navigate', to: companiesTo, labelKey: 'ux.readiness.action.documents' };
  }
  if (current === 'review' || current === 'ready') {
    if (placement === 'knowledge') return null;
    return {
      kind: 'navigate',
      to: knowledgeTo,
      labelKey: current === 'review' ? 'ux.readiness.action.review' : 'ux.readiness.action.confirm',
    };
  }
  return null;
}

