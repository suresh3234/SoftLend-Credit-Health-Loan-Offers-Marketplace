import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { AlertCircle, RefreshCw } from 'lucide-react';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import OffersList from './components/OffersList';
import styles from './App.module.css';

const API_BASE_URL = 'http://localhost:8000';
const DEFAULT_CUSTOMER_ID = 1;

export default function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [customer, setCustomer] = useState(null);
  const [scoreFactors, setScoreFactors] = useState([]);
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notification, setNotification] = useState(null);

  // Fetch all data from Backend
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch credit profile (customer info + gaps)
      const profileRes = await axios.get(`${API_BASE_URL}/customers/${DEFAULT_CUSTOMER_ID}/credit-profile`);
      setCustomer({
        id: profileRes.data.customer_id,
        name: profileRes.data.name,
        cibil_score: profileRes.data.cibil_score,
        score_fetched_at: profileRes.data.score_fetched_at
      });

      // Format factors list to match frontend needs
      const formattedFactors = profileRes.data.gaps.map(g => ({
        id: g.id,
        factor: g.factor,
        current_value: g.current_value,
        ideal_value: g.ideal_value,
        impact: g.impact,
        estimated_score_gain: g.estimated_score_gain,
        action_description: g.action_description,
        status: g.status // 'open' or 'resolved'
      }));
      setScoreFactors(formattedFactors);

      // 2. Fetch loan offers
      const offersRes = await axios.get(`${API_BASE_URL}/customers/${DEFAULT_CUSTOMER_ID}/offers`);
      setOffers(offersRes.data);

    } catch (err) {
      console.error('Error fetching Softlend data:', err);
      setError(
        err.response?.data?.error || 
        'Could not connect to the backend server. Make sure the API is running at http://localhost:8000'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Handle resolving a credit gap
  const handleResolveGap = async (gapId) => {
    try {
      setLoading(true);
      
      // 1. Resolve gap on backend database
      await axios.patch(`${API_BASE_URL}/credit-gaps/${gapId}/resolve`);
      
      // Find the factor details to get score gain
      const factor = scoreFactors.find(f => f.id === gapId);
      const scoreGain = factor ? factor.estimated_score_gain : 0;
      
      // 2. Update the CIBIL score in the database
      const newScore = Math.min(900, (customer.cibil_score || 300) + scoreGain);
      await axios.post(`${API_BASE_URL}/customers/${DEFAULT_CUSTOMER_ID}/credit-score`, {
        cibil_score: newScore
      });

      showNotification(`"${factor?.factor}" resolved! Score increased by +${scoreGain} points.`);
      
      // 3. Refresh profile and offers data
      await fetchData();

    } catch (err) {
      console.error('Error resolving credit gap:', err);
      showNotification('Failed to resolve credit gap. Please try again.', true);
      setLoading(false);
    }
  };

  // Handle accepting a loan offer
  const handleAcceptOffer = async (offerId) => {
    try {
      setLoading(true);
      // Transition offer status to 'active' in database
      const res = await axios.patch(`${API_BASE_URL}/offers/${offerId}/status`, {
        status: 'active'
      });
      showNotification(`Loan offer from ${res.data.lender} accepted successfully!`);
      await fetchData();
    } catch (err) {
      console.error('Error accepting offer:', err);
      showNotification(err.response?.data?.error || 'Failed to accept offer.', true);
      setLoading(false);
    }
  };

  const showNotification = (message, isError = false) => {
    setNotification({ text: message, isError });
    setTimeout(() => {
      setNotification(null);
    }, 5000);
  };

  return (
    <div className={styles.app}>
      <Navbar 
        activeView={activeView} 
        setActiveView={setActiveView} 
        customer={customer} 
      />

      {/* GLOBAL NOTIFICATION TOAST */}
      {notification && (
        <div className={`${styles.toast} ${notification.isError ? styles.toastError : styles.toastSuccess}`}>
          <span>{notification.text}</span>
        </div>
      )}

      <main className={styles.mainContent}>
        {/* LOADING STATE */}
        {loading && (
          <div className={styles.loadingWrapper}>
            <div className={styles.skeletonHeader}></div>
            <div className={styles.skeletonGrid}>
              <div className={styles.skeletonCardLarge}></div>
              <div className={styles.skeletonCardSmall}></div>
            </div>
            <div className={styles.spinner}></div>
            <span className={styles.loadingText}>Fetching credit profile...</span>
          </div>
        )}

        {/* ERROR STATE */}
        {!loading && error && (
          <div className={styles.errorWrapper}>
            <AlertCircle size={48} className={styles.errorIcon} />
            <h2 className={styles.errorTitle}>Connection Error</h2>
            <p className={styles.errorDesc}>{error}</p>
            <button className={styles.retryBtn} onClick={fetchData}>
              <RefreshCw size={16} />
              <span>Retry Connection</span>
            </button>
          </div>
        )}

        {/* HAPPY PATH: DASHBOARD OR OFFERS VIEW */}
        {!loading && !error && (
          activeView === 'dashboard' ? (
            <Dashboard 
              customer={customer}
              scoreFactors={scoreFactors}
              offers={offers}
              onResolveGap={handleResolveGap}
            />
          ) : (
            <OffersList 
              customer={customer}
              offers={offers}
              onAcceptOffer={handleAcceptOffer}
            />
          )
        )}
      </main>
    </div>
  );
}
