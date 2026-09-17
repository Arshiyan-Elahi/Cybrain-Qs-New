import styles from './TextArea.module.css';

interface TextAreaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  'aria-label'?: string;
}

export function TextArea({
  value,
  onChange,
  placeholder,
  rows = 6,
  'aria-label': ariaLabel,
}: TextAreaProps) {
  return (
    <textarea
      className={styles.textarea}
      value={value}
      rows={rows}
      placeholder={placeholder}
      aria-label={ariaLabel ?? placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
