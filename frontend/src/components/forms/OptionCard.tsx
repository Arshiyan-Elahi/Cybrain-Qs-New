import { Icon, type IconName } from '../common/Icon';
import styles from './OptionCard.module.css';

interface OptionCardProps {
  name: string;
  value: string;
  icon: IconName;
  title: string;
  description: string;
  checked: boolean;
  onChange: (value: string) => void;
}

/**
 * Large radio card: a radio in the top-left corner, a glyph, a two-line title
 * and a supporting line. Used by the client onboarding "what do you have?" step.
 */
export function OptionCard({
  name,
  value,
  icon,
  title,
  description,
  checked,
  onChange,
}: OptionCardProps) {
  return (
    <label className={checked ? `${styles.card} ${styles.cardChecked}` : styles.card}>
      <input
        className="visuallyHidden"
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={() => onChange(value)}
      />

      <span className={checked ? `${styles.radio} ${styles.radioChecked}` : styles.radio}>
        {checked && <span className={styles.radioDot} />}
      </span>

      <span className={styles.icon}>
        <Icon name={icon} size={58} />
      </span>

      <span className={styles.title}>{title}</span>
      <span className={styles.description}>{description}</span>
    </label>
  );
}
