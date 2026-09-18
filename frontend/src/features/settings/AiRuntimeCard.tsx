import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getAiRuntime, type AiRuntime } from '../../services/ai';
import { ApiError } from '../../services/apiClient';
import styles from './AiRuntimeCard.module.css';

function formatCheckedAt(value: string | null, locale: string): string {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function AiRuntimeCard() {
  const { t, i18n } = useTranslation();
  const [runtime, setRuntime] = useState<AiRuntime | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRuntime(await getAiRuntime());
    } catch (err) {
      setRuntime(null);
      setError(err instanceof ApiError ? err.message : t('aiRuntime.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const overallKey =
    runtime?.overall === 'healthy'
      ? 'aiRuntime.overall.healthy'
      : runtime?.overall === 'fallback_active'
        ? 'aiRuntime.overall.fallback'
        : 'aiRuntime.overall.degraded';

  return (
    <section className={styles.card} aria-labelledby="ai-runtime-title">
      <div className={styles.header}>
        <h2 id="ai-runtime-title" className={styles.title}>
          {t('aiRuntime.title')}
        </h2>
        <button type="button" className={styles.refresh} onClick={() => void load()} disabled={loading}>
          {t('aiRuntime.refresh')}
        </button>
      </div>

      {loading && !runtime ? <p className={styles.muted}>{t('aiRuntime.loading')}</p> : null}
      {error ? <p className={styles.error}>{error}</p> : null}

      {runtime ? (
        <dl className={styles.grid}>
          <div className={styles.row}>
            <dt>{t('aiRuntime.system')}</dt>
            <dd data-tone={runtime.overall}>{t(overallKey)}</dd>
          </div>
          <div className={styles.row}>
            <dt>{t('aiRuntime.remote')}</dt>
            <dd data-tone={runtime.remote.status}>
              {runtime.remote.status === 'online'
                ? t('aiRuntime.status.online')
                : t('aiRuntime.status.offline')}
            </dd>
          </div>
          <div className={styles.row}>
            <dt>{t('aiRuntime.fallbackMode')}</dt>
            <dd>
              {runtime.overall === 'fallback_active'
                ? t('aiRuntime.fallbackActive')
                : t('aiRuntime.fallbackIdle')}
            </dd>
          </div>
          <div className={styles.row}>
            <dt>{t('aiRuntime.llm')}</dt>
            <dd>
              {runtime.llm.model}
              <span className={styles.source}>
                {runtime.llm.active === 'gemini'
                  ? t('aiRuntime.source.gemini')
                  : t('aiRuntime.source.remote')}
              </span>
            </dd>
          </div>
          <div className={styles.row}>
            <dt>{t('aiRuntime.embeddings')}</dt>
            <dd>
              {t('aiRuntime.embeddingLine', {
                model: runtime.embedding.model,
                dims: runtime.embedding.dimensions,
                source:
                  runtime.embedding.active === 'local'
                    ? t('aiRuntime.source.local')
                    : t('aiRuntime.source.remote'),
              })}
            </dd>
          </div>
          <div className={styles.row}>
            <dt>{t('aiRuntime.geminiFallback')}</dt>
            <dd>
              {runtime.llm.fallback === 'ready'
                ? t('aiRuntime.readiness.ready')
                : t('aiRuntime.readiness.unavailable')}
            </dd>
          </div>
          <div className={styles.row}>
            <dt>{t('aiRuntime.localEmbedding')}</dt>
            <dd>
              {runtime.embedding.local === 'ready'
                ? t('aiRuntime.readiness.ready')
                : t('aiRuntime.readiness.unavailable')}
              {runtime.mode === 'auto' && !runtime.embedding.compatible
                ? ` · ${t('aiRuntime.incompatible')}`
                : null}
            </dd>
          </div>
          <div className={styles.row}>
            <dt>{t('aiRuntime.lastCheck')}</dt>
            <dd>{formatCheckedAt(runtime.last_health_check, i18n.language)}</dd>
          </div>
          {runtime.fallback_reason ? (
            <div className={styles.row}>
              <dt>{t('aiRuntime.reason')}</dt>
              <dd className={styles.reason}>{runtime.fallback_reason}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </section>
  );
}
