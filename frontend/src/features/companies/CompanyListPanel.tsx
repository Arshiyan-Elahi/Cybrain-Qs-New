import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { Icon } from '../../components/common/Icon';
import { SearchInput } from '../../components/common/SearchInput';
import type { Company } from '../../types';
import { CompanyListItem } from './CompanyListItem';
import styles from './CompanyListPanel.module.css';

interface CompanyListPanelProps {
  companies: Company[];
  selectedId: string | null;
  query: string;
  loading?: boolean;
  onQueryChange: (value: string) => void;
  onSelect: (id: string) => void;
  onCreate: () => void;
}

/** Left column of the company profiles screen: search + selectable list. */
export function CompanyListPanel({
  companies,
  selectedId,
  query,
  loading = false,
  onQueryChange,
  onSelect,
  onCreate,
}: CompanyListPanelProps) {
  const { t } = useTranslation();

  return (
    <section className={styles.panel}>
      <div className={styles.search}>
        <SearchInput
          value={query}
          onChange={onQueryChange}
          placeholder={t('companyProfiles.searchPlaceholder')}
          aria-label={t('companyProfiles.searchLabel')}
        />
      </div>

      {companies.length > 0 ? (
        <ul className={styles.list}>
          {companies.map((company) => (
            <CompanyListItem
              key={company.id}
              company={company}
              selected={company.id === selectedId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      ) : (
        <p className={styles.empty}>
          {loading ? t('common.loading') : t('companyProfiles.empty')}
        </p>
      )}

      <div className={styles.footer}>
        <Button
          variant="outline"
          block
          leadingIcon={<Icon name="plus" size={22} strokeWidth={2.2} />}
          onClick={onCreate}
        >
          {t('companyProfiles.createCompany')}
        </Button>
      </div>
    </section>
  );
}
