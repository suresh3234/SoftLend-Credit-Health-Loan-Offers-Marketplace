import React, { useState } from 'react';
import { Sparkles, TrendingUp, CheckCircle, AlertTriangle, HelpCircle, Lock, Unlock } from 'lucide-react';
import styles from './Dashboard.module.css';

export default function Dashboard({ customer, scoreFactors, offers, onResolveGap }) {
  // Simulator State: Track ID of gaps selected for simulation
  const [selectedGaps, setSelectedGaps] = useState({});

  if (!customer) return null;

  const currentScore = customer.cibil_score || 300;
  const lastUpdated = customer.score_fetched_at 
    ? new Date(customer.score_fetched_at).toLocaleDateString('en-IN', {
        year: 'numeric', month: 'long', day: 'numeric'
      })
    : 'Not available';

  // Toggle gap resolution in simulator
  const handleToggleSimulator = (factorId, estimatedGain) => {
    setSelectedGaps(prev => ({
      ...prev,
      [factorId]: !prev[factorId]
    }));
  };

  // Calculate simulated score
  const simulatedScoreGain = scoreFactors.reduce((total, factor) => {
    if (selectedGaps[factor.id]) {
      return total + factor.estimated_score_gain;
    }
    return total;
  }, 0);
  const simulatedScore = Math.min(900, currentScore + simulatedScoreGain);

  // Maximum potential score (resolving all gaps)
  const maxPotentialGain = scoreFactors.reduce((total, f) => {
    if (f.status === 'open') {
      return total + f.estimated_score_gain;
    }
    return total;
  }, 0);
  const maxPotentialScore = Math.min(900, currentScore + maxPotentialGain);

  // Get score health status text and colors
  const getScoreInfo = (score) => {
    if (score < 650) return { label: 'Poor', color: 'var(--color-red)', pct: (score - 300) / 600 };
    if (score < 750) return { label: 'Good', color: 'var(--color-amber)', pct: (score - 300) / 600 };
    return { label: 'Excellent', color: 'var(--color-green)', pct: (score - 300) / 600 };
  };

  const scoreInfo = getScoreInfo(currentScore);
  const simulatedScoreInfo = getScoreInfo(simulatedScore);

  // Gauge calculations
  const radius = 80;
  const stroke = 12;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (scoreInfo.pct * circumference);

  const getImpactBadgeStyle = (impact) => {
    switch (impact.toLowerCase()) {
      case 'high': return styles.badgeRed;
      case 'medium': return styles.badgeAmber;
      default: return styles.badgeGreen;
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Welcome back, {customer.name}</h1>
          <p className={styles.subtitle}>Here is your credit health report summary and recommended plan.</p>
        </div>
        <div className={styles.updatedDate}>Report updated: {lastUpdated}</div>
      </div>

      <div className={styles.grid}>
        {/* LEFT COLUMN: Score display and Simulator */}
        <div className={styles.colLeft}>
          {/* CIBIL SCORE GAUGE */}
          <div className={styles.card}>
            <h2 className={styles.cardTitle}>CIBIL Credit Score</h2>
            <div className={styles.gaugeContainer}>
              <svg height={radius * 2} width={radius * 2} className={styles.svgGauge}>
                <circle
                  stroke="rgba(255,255,255,0.03)"
                  fill="transparent"
                  strokeWidth={stroke}
                  r={normalizedRadius}
                  cx={radius}
                  cy={radius}
                />
                <circle
                  stroke={scoreInfo.color}
                  fill="transparent"
                  strokeWidth={stroke}
                  strokeDasharray={circumference + ' ' + circumference}
                  style={{ strokeDashoffset }}
                  strokeLinecap="round"
                  r={normalizedRadius}
                  cx={radius}
                  cy={radius}
                  className={styles.gaugeProgress}
                />
              </svg>
              <div className={styles.gaugeContent}>
                <span className={styles.gaugeScore}>{currentScore}</span>
                <span className={styles.gaugeStatus} style={{ color: scoreInfo.color }}>
                  {scoreInfo.label}
                </span>
              </div>
            </div>
            
            <div className={styles.potentialScoreBox}>
              <div className={styles.potentialHeader}>
                <span>Max Potential Score</span>
                <span className={styles.potentialVal}>{maxPotentialScore}</span>
              </div>
              <p className={styles.potentialDesc}>
                By resolving all high-impact credit factors, you could gain up to <strong>+{maxPotentialGain} pts</strong>.
              </p>
            </div>
          </div>

          {/* SCORE SIMULATOR ("What if?" PANEL) */}
          <div className={`${styles.card} ${styles.simulatorCard}`}>
            <div className={styles.simulatorHeader}>
              <Sparkles size={20} className={styles.simulatorIcon} />
              <h2 className={styles.cardTitle}>"What if?" Score Simulator</h2>
            </div>
            <p className={styles.simulatorIntro}>
              Select open improvement items below to see how completing them will boost your score and unlock loan offers.
            </p>

            <div className={styles.simulatorDisplay}>
              <div className={styles.simulatorScoreCol}>
                <span className={styles.simLabel}>Projected Score</span>
                <span className={styles.simScore} style={{ color: simulatedScoreInfo.color }}>
                  {simulatedScore}
                </span>
              </div>
              <div className={styles.simulatorGainCol}>
                <span className={styles.simLabel}>Projected Gain</span>
                <span className={styles.simGain} style={{ color: simulatedScoreGain > 0 ? 'var(--color-green)' : 'var(--text-muted)' }}>
                  +{simulatedScoreGain} pts
                </span>
              </div>
            </div>

            {/* Simulated Unlocked Offers */}
            <div className={styles.unlockedOffersPreview}>
              <h3 className={styles.offersPreviewTitle}>Newly Unlocked Offers</h3>
              <div className={styles.offersPreviewList}>
                {offers && offers.length > 0 ? (
                  (() => {
                    // Find offers locked at currentScore but unlocked at simulatedScore
                    const newlyUnlocked = offers.filter(o => 
                      o.min_score_required > currentScore && 
                      o.min_score_required <= simulatedScore
                    );

                    if (newlyUnlocked.length === 0) {
                      return (
                        <p className={styles.noOffersUnlocked}>
                          No new offers unlocked yet. Increase simulated score to 650, 700, or 720 to unlock.
                        </p>
                      );
                    }

                    return newlyUnlocked.map(offer => (
                      <div key={offer.id} className={styles.unlockedOfferItem}>
                        <div className={styles.unlockedOfferLeft}>
                          <Unlock size={14} className={styles.unlockIcon} />
                          <span className={styles.unlockedLender}>{offer.lender}</span>
                        </div>
                        <div className={styles.unlockedOfferRight}>
                          <span className={styles.unlockedAmount}>₹{(offer.amount / 100000).toFixed(1)}L</span>
                          <span className={styles.unlockedRate}>@{offer.interest_rate}%</span>
                        </div>
                      </div>
                    ));
                  })()
                ) : (
                  <p className={styles.noOffersUnlocked}>No offers loaded.</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Credit Factors & Action Plan */}
        <div className={styles.colRight}>
          <div className={styles.card}>
            <div className={styles.sectionHeader}>
              <TrendingUp size={22} className={styles.actionIcon} />
              <h2 className={styles.cardTitle}>Credit Improvement Plan</h2>
            </div>
            <p className={styles.actionIntro}>
              We analyzed your credit profile and found these gaps. Take actions below to improve.
            </p>

            <div className={styles.factorsList}>
              {scoreFactors.map((factor) => {
                const isSimulated = !!selectedGaps[factor.id];
                const isOpen = factor.status === 'open';

                return (
                  <div 
                    key={factor.id} 
                    className={`${styles.factorCard} ${!isOpen ? styles.resolvedCard : ''} ${isSimulated ? styles.simulatedFactor : ''}`}
                  >
                    <div className={styles.factorHeader}>
                      <div className={styles.factorTitleGroup}>
                        <h3 className={styles.factorName}>{factor.factor}</h3>
                        <span className={`${styles.impactBadge} ${getImpactBadgeStyle(factor.impact)}`}>
                          {factor.impact} impact
                        </span>
                      </div>
                      <div className={styles.scoreGainText}>
                        +{factor.estimated_score_gain} pts
                      </div>
                    </div>

                    <div className={styles.factorValues}>
                      <div className={styles.valBox}>
                        <span className={styles.valLabel}>Current</span>
                        <span className={styles.valContent}>{factor.current_value}</span>
                      </div>
                      <div className={styles.valBox}>
                        <span className={styles.valLabel}>Ideal Target</span>
                        <span className={styles.valContent}>{factor.ideal_value}</span>
                      </div>
                    </div>

                    <p className={styles.actionDescription}>{factor.action_description}</p>

                    {isOpen ? (
                      <div className={styles.cardActions}>
                        <label className={styles.checkboxLabel}>
                          <input 
                            type="checkbox" 
                            checked={isSimulated}
                            onChange={() => handleToggleSimulator(factor.id, factor.estimated_score_gain)}
                            className={styles.checkboxInput}
                          />
                          <span className={styles.checkboxText}>Simulate resolution</span>
                        </label>
                        <button 
                          className={styles.resolveButton} 
                          onClick={() => onResolveGap(factor.id)}
                        >
                          Resolve Now
                        </button>
                      </div>
                    ) : (
                      <div className={styles.resolvedBadge}>
                        <CheckCircle size={16} color="var(--color-green)" />
                        <span>Completed & Resolved</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
