import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import layoutStyles from './OnboardingStepLayout.module.css';

interface OnboardingFilesFieldProps {
  files: File[];
  accept?: string;
  multiple?: boolean;
  onChange: (files: File[]) => void;
  addLabel: string;
  emptyLabel: string;
  removeLabel: string;
}

function fileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

/** Local file picker for onboarding — uploads happen only after company create. */
export function OnboardingFilesField({
  files,
  accept = '.pdf,.docx',
  multiple = true,
  onChange,
  addLabel,
  emptyLabel,
  removeLabel,
}: OnboardingFilesFieldProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const selected = Array.from(list);
    const existing = new Set(files.map(fileKey));
    const merged = multiple
      ? [...files, ...selected.filter((file) => !existing.has(fileKey(file)))]
      : selected.slice(0, 1);
    onChange(merged);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className={layoutStyles.uploadZone}>
      <div>
        <Button variant="outline" size="xs" onClick={() => inputRef.current?.click()}>
          {addLabel}
        </Button>
        <input
          ref={inputRef}
          className="visuallyHidden"
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(event) => handleFiles(event.target.files)}
        />
      </div>
      {files.length === 0 ? (
        <p className={layoutStyles.helper}>{emptyLabel}</p>
      ) : (
        <ul className={layoutStyles.fileList} aria-label={t('onboarding.files.listLabel')}>
          {files.map((file) => (
            <li key={fileKey(file)} className={layoutStyles.fileRow}>
              <span>{file.name}</span>
              <Button
                variant="neutral"
                size="xs"
                onClick={() => onChange(files.filter((entry) => fileKey(entry) !== fileKey(file)))}
              >
                {removeLabel}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
