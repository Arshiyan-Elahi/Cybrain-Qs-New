import { Fragment, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { Icon } from '../../components/common/Icon';
import { StatusBadge } from '../../components/common/StatusBadge';
import { deleteCompany } from '../../services/companies';
import { formatDate } from '../../utils/formatDate';
import type { Company } from '../../types';
import { CompanyReadiness } from './CompanyReadiness';
import { SopCountCard } from './SopCountCard';
import styles from './CompanyDetailCard.module.css';

interface CompanyDetailCardProps {
  company: Company;
  /** Called after a change that should refresh the list (e.g. an upload). */
  onChanged?: () => void;
  /** Called after the company was permanently deleted. */
  onDeleted?: (company: Company) => void;
}

/** Fixed column widths measured from the design's meta strip. */
const META_WIDTHS = ['96px', '162px', undefined];

export function CompanyDetailCard({ company, onChanged, onDeleted }: CompanyDetailCardProps) {
  const { t, i18n } = useTranslation();
  const menuId = useId();
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmName, setConfirmName] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const metaFields = [
    { label: t('companyDetail.industry'), value: t(`companyData.industry.${company.industryKey}`) },
    { label: t('companyDetail.location'), value: t(`companyData.location.${company.locationKey}`) },
    {
      label: t('companyDetail.primaryLanguage'),
      value: t(`companyData.language.${company.primaryLanguageKey}`),
    },
  ];

  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen]);

  useEffect(() => {
    setMenuOpen(false);
    setConfirmOpen(false);
    setConfirmName('');
    setDeleteError(null);
    setDeleting(false);
  }, [company.id]);

  const nameMatches = confirmName.trim() === company.name;
  const canDelete = nameMatches && !deleting;

  const openConfirm = () => {
    setMenuOpen(false);
    setConfirmName('');
    setDeleteError(null);
    setConfirmOpen(true);
  };

  const handleDelete = async () => {
    if (!canDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteCompany(company.id);
      setConfirmOpen(false);
      onDeleted?.(company);
    } catch (caught) {
      setDeleteError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <span className={styles.avatar}>
          <Icon name="buildingSolid" size={62} />
        </span>

        <div className={styles.headerText}>
          <div className={styles.titleRow}>
            <h2 className={styles.name}>{company.name}</h2>
            <div className={styles.menu} ref={menuRef}>
              <button
                type="button"
                className={styles.menuButton}
                aria-label={t('companyDetail.actionsMenu')}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-controls={menuId}
                onClick={() => setMenuOpen((open) => !open)}
              >
                <Icon name="moreVertical" size={20} />
              </button>
              {menuOpen && (
                <div id={menuId} className={styles.menuPopover} role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    className={styles.menuItemDanger}
                    onClick={openConfirm}
                  >
                    {t('companyDetail.deleteCompany')}
                  </button>
                </div>
              )}
            </div>
          </div>

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

      <CompanyReadiness companyId={company.id} companyName={company.name} embedded />

      <SopCountCard companyId={company.id} focus="documents" onChanged={onChanged} />

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

      {confirmOpen && (
        <div
          className={styles.modalBackdrop}
          role="presentation"
          onMouseDown={() => !deleting && setConfirmOpen(false)}
        >
          <section
            className={styles.confirmModal}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-company-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h3 id="delete-company-title">{t('companyDetail.deleteCompanyTitle')}</h3>
            <p>{t('companyDetail.deleteCompanyLead')}</p>
            <p className={styles.confirmCompanyName}>{company.name}</p>
            <p>{t('companyDetail.deleteCompanyWarning')}</p>
            <details>
              <summary>{t('ux.details')}</summary>
              <p>{t('companyDetail.deleteCompanyWarningAdvanced')}</p>
            </details>
            <label className={styles.confirmLabel} htmlFor="delete-company-name">
              {t('companyDetail.deleteCompanyConfirmLabel', { name: company.name })}
            </label>
            <input
              id="delete-company-name"
              className={styles.confirmInput}
              value={confirmName}
              autoComplete="off"
              disabled={deleting}
              placeholder={company.name}
              onChange={(event) => setConfirmName(event.target.value)}
            />
            {deleteError && (
              <p className={styles.deleteError} role="alert">
                {deleteError}
              </p>
            )}
            <div className={styles.confirmActions}>
              <Button
                variant="neutral"
                size="sm"
                disabled={deleting}
                onClick={() => setConfirmOpen(false)}
              >
                {t('companyDetail.deleteCompanyCancel')}
              </Button>
              <Button
                size="sm"
                className={styles.deletePermanently}
                disabled={!canDelete}
                onClick={() => void handleDelete()}
              >
                {deleting
                  ? t('companyDetail.deletingCompany')
                  : t('companyDetail.deleteCompanyPermanently')}
              </Button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
