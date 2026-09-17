import { useTranslation } from 'react-i18next';
import { Icon } from '../../components/common/Icon';
import { formatDate } from '../../utils/formatDate';
import type { Company } from '../../types';
import styles from './CompanyListItem.module.css';

interface CompanyListItemProps {
  company: Company;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function CompanyListItem({ company, selected, onSelect }: CompanyListItemProps) {
  const { t, i18n } = useTranslation();

  return (
    <li>
      <button
        type="button"
        className={selected ? `${styles.row} ${styles.rowSelected}` : styles.row}
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(company.id)}
      >
        <span className={styles.tile}>
          <Icon name="buildingSolid" size={26} />
        </span>
        <span className={styles.text}>
          <span className={styles.name}>{company.name}</span>
          <span className={styles.meta}>
            {t('companyProfiles.sopCount', { count: company.sopCount })} -{' '}
            {t('companyProfiles.createdShort')}: {formatDate(company.createdAt, i18n.language)}
          </span>
        </span>
        <Icon name="chevronRight" size={20} strokeWidth={1.8} className={styles.chevron} />
      </button>
    </li>
  );
}
