import { Fragment } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from '../../components/common/Icon';
import { StatusBadge } from '../../components/common/StatusBadge';
import { formatDate } from '../../utils/formatDate';
import type { Company } from '../../types';
import { SopCountCard } from './SopCountCard';
import styles from './CompanyDetailCard.module.css';

interface CompanyDetailCardProps {
  company: Company;
  /** Called after a change that should refresh the list (e.g. an upload). */
  onChanged?: () => void;
}

/** Fixed column widths measured from the design's meta strip. */
const META_WIDTHS = ['96px', '162px', undefined];

export function CompanyDetailCard({ company, onChanged }: CompanyDetailCardProps) {
  const { t, i18n } = useTranslation();

  const metaFields = [
    { label: t('companyDetail.industry'), value: t(`companyData.industry.${company.industryKey}`) },
    { label: t('companyDetail.location'), value: t(`companyData.location.${company.locationKey}`) },
    {
      label: t('companyDetail.primaryLanguage'),
      value: t(`companyData.language.${company.primaryLanguageKey}`),
    },
  ];

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <span className={styles.avatar}>
          <Icon name="buildingSolid" size={62} />
        </span>

        <div className={styles.headerText}>
          <h2 className={styles.name}>{company.name}</h2>

          <dl className={styles.metaRow}>
            {metaFields.map((field, index) => (
              <Fragment key={field.label}>
                {index > 0 && <span className={styles.metaDivider} aria-hidden />}
                <div className={styles.metaField} style={{ width: META_WIDTHS[index] }}>
                  <dt className={styles.metaLabel}>{field.label}</dt>
                  <dd className={styles.metaValue}>{field.value}</dd>
                </div>
              </Fragment>
            ))}
          </dl>
        </div>
      </header>

      <hr className={styles.rule} />

      <h3 className={styles.sectionTitle}>{t('companyDetail.regulations')}</h3>
      <ul className={styles.badges}>
        {company.regulationIds.map((regulationId) => (
          <li key={regulationId}>
            <StatusBadge>{t(`companyData.regulation.${regulationId}`)}</StatusBadge>
          </li>
        ))}
      </ul>

      <hr className={styles.rule} />

      <SopCountCard companyId={company.id} onChanged={onChanged} />

      <hr className={styles.rule} />

      <dl className={styles.dates}>
        <div>
          <dt className={styles.dateLabel}>{t('companyDetail.createdAt')}</dt>
          <dd className={styles.dateValue}>{formatDate(company.createdAt, i18n.language)}</dd>
        </div>
        <div>
          <dt className={styles.dateLabel}>{t('companyDetail.updatedAt')}</dt>
          <dd className={styles.dateValue}>{formatDate(company.updatedAt, i18n.language)}</dd>
        </div>
      </dl>
    </section>
  );
}
