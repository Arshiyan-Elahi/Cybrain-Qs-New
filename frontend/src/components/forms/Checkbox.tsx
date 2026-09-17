import { Icon } from '../common/Icon';
import styles from './Checkbox.module.css';

interface CheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/** 16px square checkbox with a purple filled checked state. */
export function Checkbox({ label, checked, onChange }: CheckboxProps) {
  return (
    <label className={styles.option}>
      <input
        className="visuallyHidden"
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className={checked ? `${styles.box} ${styles.boxChecked}` : styles.box}>
        {checked && <Icon name="check" size={12} strokeWidth={3} />}
      </span>
      <span className={styles.label}>{label}</span>
    </label>
  );
}
