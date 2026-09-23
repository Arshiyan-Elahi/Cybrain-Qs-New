import { useTranslation } from 'react-i18next';
import type { Company } from '../../types';
import styles from './CompanySelect.module.css';

interface CompanySelectProps {
  companies: Company[];
  value: string;
  onChange: (companyId: string) => void;
  disabled?: boolean;
}

/** Company picker shared by Company Knowledge and SOPs. */
export function CompanySelect({ companies, value, onChange, disabled = false }: CompanySelectProps) {
  const { t } = useTranslation();

  if (companies.length === 0) return null;

  return (
    <label className={styles.field}>
      <span className={styles.label}>{t('ux.companySelect.label')}</span>
      <select
        className={styles.select}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {companies.map((company) => (
          <option key={company.id} value={company.id}>
            {company.name}
          </option>
        ))}
      </select>
    </label>
  );
}
