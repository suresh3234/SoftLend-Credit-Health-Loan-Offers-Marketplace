CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(100) NOT NULL,
  mobile VARCHAR(15) NOT NULL UNIQUE,
  pan VARCHAR(10) NOT NULL,
  cibil_score INTEGER DEFAULT NULL,
  score_fetched_at TIMESTAMP DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credit_gaps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL,
  factor VARCHAR(100) NOT NULL,
  current_value VARCHAR(100) NOT NULL,
  ideal_value VARCHAR(100) NOT NULL,
  impact VARCHAR(20) CHECK(impact IN ('high', 'medium', 'low')) NOT NULL,
  estimated_score_gain INTEGER NOT NULL,
  action_description TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'open' CHECK(status IN ('open', 'resolved')),
  resolved_at TIMESTAMP DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS offers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL,
  lender VARCHAR(100) NOT NULL,
  amount DECIMAL(12, 2) NOT NULL,
  interest_rate DECIMAL(5, 2) NOT NULL,
  tenure_months INTEGER NOT NULL,
  min_score_required INTEGER NOT NULL DEFAULT 650,
  status VARCHAR(20) DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'disbursed')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);
