import { useTranslation } from 'react-i18next';
import { Icon } from '../common/Icon';
import type { SopTitleSuggestion } from '../../types';
import styles from './SopSuggestionList.module.css';

interface SopSuggestionListProps {
  suggestions: SopTitleSuggestion[];
  /** Receives the resolved label so it can be written into the title field. */
  onSelect: (label: string) => void;
}

/** "Suggestions based on existing SOPs" — two-column link list. */
export function SopSuggestionList({ suggestions, onSelect }: SopSuggestionListProps) {
  const { t } = useTranslation();

  return (
    <ul className={styles.list}>
      {suggestions.map((suggestion) => {
        const label = t(suggestion.labelKey);
        return (
          <li key={suggestion.id}>
            <button type="button" className={styles.item} onClick={() => onSelect(label)}>
              <Icon name="fileText" size={15} strokeWidth={1.7} className={styles.icon} />
              <span>{label}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
