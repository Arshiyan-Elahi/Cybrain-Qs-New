import { useState, type FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/common/Button';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { Wordmark } from '../components/layout/Wordmark';
import { ApiError } from '../services/apiClient';
import { useAuth } from '../features/auth/useAuth';
import { ROUTES } from '../constants/navigation';
import styles from './LoginPage.module.css';

/**
 * Sign in / sign up.
 *
 * NOT FROM A DESIGN — no login screen exists in the source PDFs. Built from the
 * existing design tokens and components so it belongs visually, and kept
 * deliberately minimal so replacing it with a real design is cheap.
 */
export function LoginPage() {
  const { t } = useTranslation();
  const { user, loading, signIn, signUp } = useAuth();
  const location = useLocation();

  const [mode, setMode] = useState<'signIn' | 'signUp'>('signIn');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return null;
  if (user) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from ?? ROUTES.companies} replace />;
  }

  const isSignUp = mode === 'signUp';

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isSignUp) await signUp(email, password, fullName);
      else await signIn(email, password);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : t('auth.errors.unreachable'),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.switcher}>
        <LanguageSwitcher />
      </div>

      <div className={styles.card}>
        <Wordmark />

        <h1 className={styles.title}>{isSignUp ? t('auth.signUpTitle') : t('auth.signInTitle')}</h1>
        <p className={styles.subtitle}>
          {isSignUp ? t('auth.signUpSubtitle') : t('auth.signInSubtitle')}
        </p>

        <form className={styles.form} onSubmit={handleSubmit}>
          {isSignUp && (
            <label className={styles.field}>
              <span className={styles.label}>{t('auth.fullName')}</span>
              <input
                className={styles.input}
                type="text"
                value={fullName}
                autoComplete="name"
                required
                onChange={(event) => setFullName(event.target.value)}
              />
            </label>
          )}

          <label className={styles.field}>
            <span className={styles.label}>{t('auth.email')}</span>
            <input
              className={styles.input}
              type="email"
              value={email}
              autoComplete="email"
              required
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>{t('auth.password')}</span>
            <input
              className={styles.input}
              type="password"
              value={password}
              autoComplete={isSignUp ? 'new-password' : 'current-password'}
              required
              minLength={isSignUp ? 8 : undefined}
              onChange={(event) => setPassword(event.target.value)}
            />
            {isSignUp && <span className={styles.hint}>{t('auth.passwordHint')}</span>}
          </label>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          <Button type="submit" block disabled={busy}>
            {busy
              ? t('auth.working')
              : isSignUp
                ? t('auth.signUpAction')
                : t('auth.signInAction')}
          </Button>
        </form>

        <button
          type="button"
          className={styles.toggle}
          onClick={() => {
            setMode(isSignUp ? 'signIn' : 'signUp');
            setError(null);
          }}
        >
          {isSignUp ? t('auth.haveAccount') : t('auth.needAccount')}
        </button>
      </div>
    </div>
  );
}
