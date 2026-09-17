import { Icon } from './Icon';
import styles from './SearchInput.module.css';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  'aria-label'?: string;
}

/**
 * Search field for the company list. The design places a plus glyph rather
 * than a magnifier inside this field, which is reproduced here as drawn.
 */
export function SearchInput({
  value,
  onChange,
  placeholder,
  'aria-label': ariaLabel,
}: SearchInputProps) {
  return (
    <div className={styles.wrapper}>
      <Icon name="plus" size={17} strokeWidth={2.2} />
      <input
        className={styles.input}
        type="search"
        value={value}
        placeholder={placeholder}
        aria-label={ariaLabel ?? placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
