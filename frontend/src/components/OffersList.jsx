import React, { useState, useEffect } from 'react';
import { Search, Lock, ShieldAlert, BadgeInfo, Check, Sparkles, X, Calculator } from 'lucide-react';
import styles from './OffersList.module.css';

export default function OffersList({ customer, offers, onAcceptOffer }) {
  const [filter, setFilter] = useState('all'); // 'all', 'unlocked', 'locked'
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedOffer, setSelectedOffer] = useState(null); // For Accept modal
  const [calculatorOffer, setCalculatorOffer] = useState(null); // For EMI Calculator modal

  // Interactive Calculator State
  const [calcAmount, setCalcAmount] = useState(300000);
  const [calcRate, setCalcRate] = useState(12.5);
  const [calcTenure, setCalcTenure] = useState(36);

  // CIBIL Score check
  const cibilScore = customer ? (customer.cibil_score || 0) : 0;

  // Debounce search query (300ms)
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);

    return () => {
      clearTimeout(handler);
    };
  }, [searchQuery]);

  // Format currency in Indian Rupees format (₹ Lakhs/Crores or standard formatting)
  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);
  };

  // Filter and Search offers
  const filteredOffers = offers.filter(offer => {
    const isLocked = cibilScore < offer.min_score_required;
    
    // Status filter
    if (filter === 'unlocked' && isLocked) return false;
    if (filter === 'locked' && !isLocked) return false;

    // Search filter
    if (debouncedSearch && !offer.lender.toLowerCase().includes(debouncedSearch.toLowerCase())) {
      return false;
    }

    return true;
  });

  // Calculate live EMI for the calculator
  const calculateLiveEMI = (principal, rate, tenure) => {
    const r = rate / 12 / 100;
    const n = tenure;
    if (r > 0) {
      return (principal * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
    }
    return principal / n;
  };

  const calculatedEMI = calculateLiveEMI(calcAmount, calcRate, calcTenure);

  // Open interactive calculator for a specific offer
  const openCalculator = (offer) => {
    setCalculatorOffer(offer);
    setCalcAmount(offer.amount);
    setCalcRate(offer.interest_rate);
    setCalcTenure(offer.tenure_months);
  };

  return (
    <div className={styles.container}>
      {/* Header and Controls */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Personalized Loan Offers</h1>
          <p className={styles.subtitle}>
            Explore and compare loans from India's top lenders tailored for your profile.
          </p>
        </div>
        
        {/* SCORE STATUS MESSAGE */}
        {cibilScore < 650 && (
          <div className={styles.scoreWarning}>
            <ShieldAlert size={16} />
            <span>Score below 650. Solve credit gaps to unlock offers!</span>
          </div>
        )}
      </div>

      {/* FILTER & SEARCH BAR */}
      <div className={styles.controlsRow}>
        <div className={styles.searchWrapper}>
          <Search size={18} className={styles.searchIcon} />
          <input
            type="text"
            placeholder="Search lenders (e.g. HDFC)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={styles.searchInput}
          />
        </div>

        <div className={styles.filtersGroup}>
          <button
            className={`${styles.filterBtn} ${filter === 'all' ? styles.activeFilter : ''}`}
            onClick={() => setFilter('all')}
          >
            All Offers ({offers.length})
          </button>
          <button
            className={`${styles.filterBtn} ${filter === 'unlocked' ? styles.activeFilter : ''}`}
            onClick={() => setFilter('unlocked')}
          >
            Unlocked ({offers.filter(o => cibilScore >= o.min_score_required).length})
          </button>
          <button
            className={`${styles.filterBtn} ${filter === 'locked' ? styles.activeFilter : ''}`}
            onClick={() => setFilter('locked')}
          >
            Locked ({offers.filter(o => cibilScore < o.min_score_required).length})
          </button>
        </div>
      </div>

      {/* OFFERS LISTING */}
      {filteredOffers.length === 0 ? (
        <div className={styles.emptyState}>
          <BadgeInfo size={40} className={styles.emptyIcon} />
          <h3 className={styles.emptyTitle}>No Offers Match Filters</h3>
          <p className={styles.emptyDesc}>
            {offers.length === 0 
              ? "No offers available yet. Improve your credit score to unlock offers." 
              : "Try adjusting your search criteria or improve your credit score."}
          </p>
        </div>
      ) : (
        <div className={styles.offersGrid}>
          {filteredOffers.map((offer) => {
            const isLocked = cibilScore < offer.min_score_required;
            const scoreGap = offer.min_score_required - cibilScore;

            return (
              <div 
                key={offer.id} 
                className={`${styles.offerCard} ${isLocked ? styles.lockedCard : ''}`}
              >
                {isLocked && (
                  <div className={styles.lockedOverlay}>
                    <Lock size={20} className={styles.lockIcon} />
                    <span className={styles.lockedLabel}>Locked Offer</span>
                    <span className={styles.lockedSubtext}>
                      Improve score by <strong>{scoreGap} pts</strong> to unlock
                    </span>
                  </div>
                )}

                {/* Offer Details */}
                <div className={styles.cardHeader}>
                  <div>
                    <h3 className={styles.lenderName}>{offer.lender}</h3>
                    <span className={styles.statusBadge}>{offer.status}</span>
                  </div>
                  <div className={styles.amountText}>{formatCurrency(offer.amount)}</div>
                </div>

                <div className={styles.offerMetrics}>
                  <div className={styles.metricItem}>
                    <span className={styles.metricLabel}>Interest Rate</span>
                    <span className={styles.metricVal}>{offer.interest_rate}% p.a.</span>
                  </div>
                  <div className={styles.metricItem}>
                    <span className={styles.metricLabel}>Tenure</span>
                    <span className={styles.metricVal}>{offer.tenure_months} Months</span>
                  </div>
                  <div className={styles.metricItem}>
                    <span className={styles.metricLabel}>Monthly EMI</span>
                    <span className={styles.metricVal}>{formatCurrency(offer.emi)}</span>
                  </div>
                </div>

                <div className={styles.cardFooter}>
                  <button 
                    className={styles.calculatorBtn}
                    onClick={() => openCalculator(offer)}
                    title="Open EMI Calculator"
                  >
                    <Calculator size={16} />
                    <span>Calculate EMI</span>
                  </button>
                  
                  <button
                    className={styles.acceptBtn}
                    disabled={isLocked}
                    onClick={() => setSelectedOffer(offer)}
                  >
                    {isLocked ? 'Locked' : 'Accept Offer'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* CONFIRMATION MODAL */}
      {selectedOffer && (
        <div className={styles.modalOverlay}>
          <div className={styles.modal}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Confirm Loan Agreement</h3>
              <button className={styles.closeBtn} onClick={() => setSelectedOffer(null)}>
                <X size={18} />
              </button>
            </div>
            <div className={styles.modalBody}>
              <p className={styles.modalIntro}>
                You are accepting the loan offer from <strong>{selectedOffer.lender}</strong>. Here are the terms:
              </p>
              
              <div className={styles.termsList}>
                <div className={styles.termRow}>
                  <span>Principal Amount:</span>
                  <strong>{formatCurrency(selectedOffer.amount)}</strong>
                </div>
                <div className={styles.termRow}>
                  <span>Interest Rate:</span>
                  <strong>{selectedOffer.interest_rate}% p.a.</strong>
                </div>
                <div className={styles.termRow}>
                  <span>Tenure:</span>
                  <strong>{selectedOffer.tenure_months} months</strong>
                </div>
                <div className={styles.termRow}>
                  <span>Estimated Monthly EMI:</span>
                  <strong>{formatCurrency(selectedOffer.emi)}</strong>
                </div>
              </div>

              <div className={styles.agreementText}>
                By clicking confirm, you consent to the initial processing of your application. Softlend will connect you with the lender to finalize documentation.
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button 
                className={styles.cancelBtn} 
                onClick={() => setSelectedOffer(null)}
              >
                Cancel
              </button>
              <button 
                className={styles.confirmBtn}
                onClick={() => {
                  onAcceptOffer(selectedOffer.id);
                  setSelectedOffer(null);
                }}
              >
                <Check size={16} />
                <span>Confirm & Accept</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* INTERACTIVE EMI CALCULATOR MODAL */}
      {calculatorOffer && (
        <div className={styles.modalOverlay}>
          <div className={`${styles.modal} ${styles.calculatorModal}`}>
            <div className={styles.modalHeader}>
              <div className={styles.modalTitleGroup}>
                <Calculator size={18} color="var(--primary)" />
                <h3 className={styles.modalTitle}>EMI Calculator — {calculatorOffer.lender}</h3>
              </div>
              <button className={styles.closeBtn} onClick={() => setCalculatorOffer(null)}>
                <X size={18} />
              </button>
            </div>
            
            <div className={styles.modalBody}>
              {/* SLIDERS & CONTROLS */}
              <div className={styles.calcControl}>
                <div className={styles.calcLabelRow}>
                  <span>Loan Amount (P)</span>
                  <strong>{formatCurrency(calcAmount)}</strong>
                </div>
                <input 
                  type="range" 
                  min="50000" 
                  max="1500000" 
                  step="10000" 
                  value={calcAmount}
                  onChange={(e) => setCalcAmount(Number(e.target.value))}
                  className={styles.slider}
                />
              </div>

              <div className={styles.calcControl}>
                <div className={styles.calcLabelRow}>
                  <span>Interest Rate (R)</span>
                  <strong>{calcRate}% p.a.</strong>
                </div>
                <input 
                  type="range" 
                  min="5" 
                  max="25" 
                  step="0.1" 
                  value={calcRate}
                  onChange={(e) => setCalcRate(Number(e.target.value))}
                  className={styles.slider}
                />
              </div>

              <div className={styles.calcControl}>
                <div className={styles.calcLabelRow}>
                  <span>Tenure (Months)</span>
                  <strong>{calcTenure} months</strong>
                </div>
                <input 
                  type="range" 
                  min="6" 
                  max="84" 
                  step="6" 
                  value={calcTenure}
                  onChange={(e) => setCalcTenure(Number(e.target.value))}
                  className={styles.slider}
                />
              </div>

              {/* LIVE EMI DISPLAY */}
              <div className={styles.calcResultBox}>
                <span className={styles.calcResultLabel}>Calculated Monthly EMI</span>
                <span className={styles.calcResultVal}>{formatCurrency(calculatedEMI)}</span>
                <span className={styles.calcResultTotal}>
                  Total Interest: {formatCurrency((calculatedEMI * calcTenure) - calcAmount)} | Total Repayment: {formatCurrency(calculatedEMI * calcTenure)}
                </span>
              </div>
            </div>

            <div className={styles.modalFooter}>
              <button 
                className={styles.confirmBtn}
                onClick={() => setCalculatorOffer(null)}
              >
                Close Calculator
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
