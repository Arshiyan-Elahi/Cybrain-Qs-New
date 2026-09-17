import styles from './RadioOption.module.css';

interface RadioOptionProps {
  name: string;
  value: string;
  label: string;
  checked: boolean;
  onChange: (value: string) => void;
}

/** Bordered row containing a 14px ring radio, used by the client picker. */
export function RadioOption({ name, value, label, checked, onChange }: RadioOptionProps) {
  return (
    <label className={styles.option}>
      <input
        className="visuallyHidden"
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={() => onChange(value)}
      />
      <span className={checked ? `${styles.ring} ${styles.ringChecked}` : styles.ring} />
      <span className={styles.label}>{label}</span>
    </label>
  );
}
