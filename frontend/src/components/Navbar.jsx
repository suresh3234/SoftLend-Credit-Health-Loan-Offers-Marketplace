import React from 'react';
import { Shield, CreditCard, User } from 'lucide-react';
import styles from './Navbar.module.css';

export default function Navbar({ activeView, setActiveView, customer }) {
  const getScoreColor = (score) => {
    if (!score) return 'var(--text-muted)';
    if (score < 650) return 'var(--color-red)';
    if (score < 750) return 'var(--color-amber)';
    return 'var(--color-green)';
  };

  return (
    <nav className={styles.navbar}>
      <div className={styles.navContainer}>
        <div className={styles.brand} onClick={() => setActiveView('dashboard')}>
          <div className={styles.logoIcon}>
            <Shield size={24} color="var(--primary)" />
          </div>
          <span className={styles.brandName}>Soft<span className={styles.brandAccent}>lend</span></span>
        </div>

        <div className={styles.navLinks}>
          <button 
            className={`${styles.navLink} ${activeView === 'dashboard' ? styles.active : ''}`}
            onClick={() => setActiveView('dashboard')}
          >
            <Shield size={18} />
            <span>Credit Dashboard</span>
          </button>
          <button 
            className={`${styles.navLink} ${activeView === 'offers' ? styles.active : ''}`}
            onClick={() => setActiveView('offers')}
          >
            <CreditCard size={18} />
            <span>Loan Offers</span>
          </button>
        </div>

        {customer && (
          <div className={styles.userProfile}>
            <div className={styles.userInfo}>
              <span className={styles.userName}>{customer.name}</span>
              <span className={styles.userMeta}>ID: {customer.id}</span>
            </div>
            <div className={styles.scoreBadge} style={{ borderColor: getScoreColor(customer.cibil_score) }}>
              <span className={styles.scoreLabel}>CIBIL</span>
              <span className={styles.scoreVal} style={{ color: getScoreColor(customer.cibil_score) }}>
                {customer.cibil_score || 'N/A'}
              </span>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
