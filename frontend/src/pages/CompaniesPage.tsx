import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/common/Button';
import { Icon } from '../components/common/Icon';
import { InfoPanel } from '../components/common/InfoPanel';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { PageHeader } from '../components/common/PageHeader';
import { CompanyDetailCard } from '../features/companies/CompanyDetailCard';
import { CompanyListPanel } from '../features/companies/CompanyListPanel';
import { useCompanies } from '../features/companies/useCompanies';
import { ROUTES } from '../constants/navigation';
import type { Company } from '../types';
import styles from './CompaniesPage.module.css';

interface CompaniesLocationState {
  selectCompanyId?: string;
  createdCompany?: Company;
}

/** Company Profiles — the Company Profile / CKM entry screen. Live data. */
export function CompaniesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingSelectId, setPendingSelectId] = useState<string | null>(null);

  const { companies, loading, error, refresh, upsertCompany, removeCompany } = useCompanies(query);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  useEffect(() => {
    const state = (location.state ?? null) as CompaniesLocationState | null;
    if (!state?.selectCompanyId && !state?.createdCompany) return;

    const created = state.createdCompany;
    const selectId = state.selectCompanyId ?? created?.id ?? null;
    if (created) upsertCompany(created);
    if (selectId) {
      setPendingSelectId(selectId);
      setSelectedId(selectId);
    }
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.pathname, location.state, navigate, upsertCompany]);

  // Keep a valid selection as the list changes; prefer a newly created company.
  useEffect(() => {
    if (companies.length === 0) {
      // Keep pending selection while the first fetch is in flight.
      if (!pendingSelectId) setSelectedId(null);
      return;
    }
    if (pendingSelectId && companies.some((company) => company.id === pendingSelectId)) {
      setSelectedId(pendingSelectId);
      setPendingSelectId(null);
      return;
    }
    if (!selectedId || !companies.some((company) => company.id === selectedId)) {
      setSelectedId(pendingSelectId && companies.some((company) => company.id === pendingSelectId)
        ? pendingSelectId
        : companies[0].id);
    }
  }, [companies, pendingSelectId, selectedId]);

  const selectedCompany = companies.find((company) => company.id === selectedId) ?? null;

  const handleCompanyDeleted = (company: Company) => {
    const remaining = companies.filter((entry) => entry.id !== company.id);
    removeCompany(company.id);
    setSelectedId(remaining[0]?.id ?? null);
    setDeleteSuccess(t('companyDetail.deleteCompanySuccess', { name: company.name }));
    void refresh();
  };

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <PageHeader
          title={t('companyProfiles.title')}
          description={t('companyProfiles.description')}
          action={
            <div className={styles.headerActions}>
              <LanguageSwitcher />
              <Button
                leadingIcon={<Icon name="plus" size={22} strokeWidth={2.2} />}
                onClick={() => navigate(ROUTES.companyCreate)}
              >
                {t('companyProfiles.createCompany')}
              </Button>
            </div>
          }
        />

        {error && (
          <p className={styles.error} role="alert">
            {t('common.loadFailed', { message: error })}{' '}
            <button type="button" className={styles.retry} onClick={() => void refresh()}>
              {t('common.retry')}
            </button>
          </p>
        )}

        {deleteSuccess && (
          <p className={styles.success} role="status">
            {deleteSuccess}
          </p>
        )}

        <div className={styles.columns}>
          <CompanyListPanel
            companies={companies}
            selectedId={selectedId}
            query={query}
            loading={loading}
            onQueryChange={setQuery}
            onSelect={(id) => {
              setDeleteSuccess(null);
              setSelectedId(id);
            }}
            onCreate={() => navigate(ROUTES.companyCreate)}
          />

          {selectedCompany ? (
            <CompanyDetailCard
              company={selectedCompany}
              onChanged={refresh}
              onDeleted={handleCompanyDeleted}
            />
          ) : (
            <div className={styles.detailPlaceholder}>
              {loading || pendingSelectId ? t('common.loading') : t('companyProfiles.noSelection')}
            </div>
          )}
        </div>

        <InfoPanel title={t('companyProfiles.info.title')}>
          {t('companyProfiles.info.body')}
        </InfoPanel>
      </div>
    </div>
  );
}
