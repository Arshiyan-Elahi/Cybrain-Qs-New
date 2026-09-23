import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/common/Button';
import { Icon } from '../components/common/Icon';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { PageHeader } from '../components/common/PageHeader';
import { CompanySelect } from '../features/companies/CompanySelect';
import { KnowledgeReview } from '../features/companies/KnowledgeReview';
import { useCompanies } from '../features/companies/useCompanies';
import { ROUTES } from '../constants/navigation';
import styles from './KnowledgePage.module.css';

/** Guided review of company knowledge for non-technical QA users. */
export function KnowledgePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { companies, loading, error, refresh } = useCompanies('');
  const [selectedId, setSelectedId] = useState(params.get('company') ?? '');

  useEffect(() => {
    const fromQuery = params.get('company');
    if (fromQuery && companies.some((company) => company.id === fromQuery)) {
      setSelectedId(fromQuery);
      return;
    }
    if (!selectedId || !companies.some((company) => company.id === selectedId)) {
      setSelectedId(companies[0]?.id ?? '');
    }
  }, [companies, params, selectedId]);

  const selected = companies.find((company) => company.id === selectedId) ?? null;

  const choose = (companyId: string) => {
    setSelectedId(companyId);
    setParams(companyId ? { company: companyId } : {});
  };

  return (
    <div className={styles.page}>
      <PageHeader
        title={t('ux.knowledge.title')}
        description={t('ux.knowledge.description')}
        action={<LanguageSwitcher />}
      />

      {error && (
        <p className={styles.error} role="alert">
          {t('common.loadFailed', { message: error })}{' '}
          <button type="button" className={styles.retry} onClick={() => void refresh()}>
            {t('common.retry')}
          </button>
        </p>
      )}

      {loading && companies.length === 0 && <p className={styles.note}>{t('common.loading')}</p>}

      {!loading && companies.length === 0 && (
        <div className={styles.empty}>
          <h2>{t('ux.knowledge.emptyTitle')}</h2>
          <p>{t('ux.knowledge.emptyBody')}</p>
          <Button
            leadingIcon={<Icon name="plus" size={22} strokeWidth={2.2} />}
            onClick={() => navigate(ROUTES.companyCreate)}
          >
            {t('companyProfiles.createCompany')}
          </Button>
        </div>
      )}

      {selected && (
        <div className={styles.stack}>
          <CompanySelect companies={companies} value={selected.id} onChange={choose} />
          <KnowledgeReview companyId={selected.id} companyName={selected.name} />
        </div>
      )}
    </div>
  );
}
