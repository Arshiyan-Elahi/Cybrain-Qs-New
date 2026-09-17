import styles from './TextField.module.css';

interface TextFieldProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  'aria-label'?: string;
}

/** Single-line input, 41px tall as measured in the wizard. */
export function TextField({
  value,
  onChange,
  placeholder,
  'aria-label': ariaLabel,
}: TextFieldProps) {
  return (
    <input
      className={styles.input}
      type="text"
      value={value}
      placeholder={placeholder}
      aria-label={ariaLabel ?? placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
