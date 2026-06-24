import unittest
import yaml
import json
from engine import run_gap_analysis, run_eligibility_evaluation

# Sample rules.yaml contents for testing
TEST_RULES_YAML = """
gap_rules: 
  - id: high_utilisation 
    field: credit_utilisation_pct 
    operator: gt 
    value: 30 
    impact: high 
    estimated_score_gain: 35 
    action_template: "Reduce credit card utilisation from {current_value}% to below 30%"
  - id: missed_payments 
    field: missed_payments_12m 
    operator: gt 
    value: 0 
    impact: high 
    estimated_score_gain: 25 
    action_template: "Clear {current_value} overdue EMI(s) to remove missed payment flag" 
  - id: written_off_account 
    field: written_off_accounts 
    operator: gt 
    value: 0 
    impact: high 
    estimated_score_gain: 40 
    action_template: "Settle {current_value} written-off account(s) with lender" 
  - id: short_credit_age 
    field: credit_age_months 
    operator: lt 
    value: 36 
    impact: medium 
    estimated_score_gain: 10 
    action_template: "Avoid closing old accounts — your oldest account is only {current_value} months old" 
  - id: too_many_enquiries 
    field: hard_enquiries_6m 
    operator: gt 
    value: 3 
    impact: medium 
    estimated_score_gain: 10 
    action_template: "Avoid applying for new credit — you have {current_value} hard enquiries in last 6 months" 

eligibility_rules: 
  - name: standard_eligibility 
    logic: AND 
    rules: 
      - id: age 
        field: age 
        operator: between 
        min: 21 
        max: 60 
        message: "Age must be between 21 and 60" 
        weight: 0.1
      - id: cibil_score 
        field: cibil_score 
        operator: gte 
        value: 650 
        message: "CIBIL score must be at least 650" 
        weight: 0.3
      - id: foir 
        field: foir 
        operator: lte 
        value: 0.5 
        message: "FOIR (existing EMIs ÷ income) must be 0.50 or below" 
        weight: 0.2
      - id: employment_type 
        field: employment_type 
        operator: in 
        values: ["salaried", "self_employed"] 
        message: "Employment type must be salaried or self-employed" 
        weight: 0.1
      - id: no_written_off_accounts 
        field: written_off_accounts 
        operator: eq 
        value: 0 
        message: "Customer must have no written-off accounts" 
        weight: 0.2
      - id: loan_amount_cap 
        field: requested_amount 
        operator: lte_multiplier 
        multiplier_field: monthly_income 
        multiplier: 10 
        message: "Requested amount cannot exceed 10x monthly income" 
        weight: 0.1
"""

class TestRuleEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rules = yaml.safe_load(TEST_RULES_YAML)

    def test_all_gap_rules_fire(self):
        """
        Test Case 1: All 5 gap rules should fire, and the output must be
        sorted correctly: high impact first (sorted by estimated_score_gain desc),
        then medium impact.
        """
        report_input = {
            "customer_id": "C001",
            "credit_utilisation_pct": 87,
            "missed_payments_12m": 2,
            "written_off_accounts": 1,
            "credit_age_months": 12,
            "hard_enquiries_6m": 5
        }
        res = run_gap_analysis(self.rules, report_input)
        
        self.assertEqual(res["gaps_found"], 5)
        self.assertEqual(res["total_potential_score_gain"], 35 + 25 + 40 + 10 + 10)
        
        # Verify sorting:
        # High impact: written_off_account (40), high_utilisation (35), missed_payments (25)
        # Medium impact: short_credit_age (10), too_many_enquiries (10)
        expected_order = [
            "written_off_account",
            "high_utilisation",
            "missed_payments",
            "short_credit_age",
            "too_many_enquiries"
        ]
        actual_order = [g["id"] for g in res["gaps"]]
        self.assertEqual(actual_order, expected_order)

    def test_no_gaps_found(self):
        """
        Test Case 2: No gap rules should fire if values are within ideal ranges.
        """
        report_input = {
            "customer_id": "C002",
            "credit_utilisation_pct": 25,
            "missed_payments_12m": 0,
            "written_off_accounts": 0,
            "credit_age_months": 48,
            "hard_enquiries_6m": 1
        }
        res = run_gap_analysis(self.rules, report_input)
        self.assertEqual(res["gaps_found"], 0)
        self.assertEqual(len(res["gaps"]), 0)
        self.assertEqual(res["total_potential_score_gain"], 0)

    def test_action_template_substitution(self):
        """
        Test Case 3: Verify template substitutions work correctly.
        """
        report_input = {
            "customer_id": "C003",
            "credit_utilisation_pct": 87,
            "missed_payments_12m": 2,
            "written_off_accounts": 0,
            "credit_age_months": 14,
            "hard_enquiries_6m": 2
        }
        res = run_gap_analysis(self.rules, report_input)
        
        # Check high_utilisation substitution
        high_util = next(g for g in res["gaps"] if g["id"] == "high_utilisation")
        self.assertEqual(high_util["action"], "Reduce credit card utilisation from 87% to below 30%")
        
        # Check missed_payments substitution
        missed = next(g for g in res["gaps"] if g["id"] == "missed_payments")
        self.assertEqual(missed["action"], "Clear 2 overdue EMI(s) to remove missed payment flag")

    def test_all_eligibility_rules_pass(self):
        """
        Test Case 4: Verify customer meets all eligibility criteria.
        """
        profile_input = {
            "customer_id": "C001",
            "age": 29,
            "cibil_score": 720,
            "monthly_income": 60000,
            "existing_emis": 15000,
            "foir": 0.25,
            "employment_type": "salaried",
            "written_off_accounts": 0,
            "requested_amount": 400000
        }
        res = run_eligibility_evaluation(self.rules, profile_input)
        self.assertTrue(res["eligible"])
        self.assertEqual(len(res["fail_reasons"]), 0)
        self.assertEqual(res["risk_score"], 0.0)

    def test_multiple_rules_fail(self):
        """
        Test Case 5: Verify eligibility fails when multiple rules fail, and weight score is computed.
        """
        # Fails age (65 > 60), fails cibil_score (620 < 650), fails foir (0.6 > 0.5)
        # Weights of failed: age (0.1) + cibil_score (0.3) + foir (0.2) = 0.6
        # Total weights: age (0.1) + cibil_score (0.3) + foir (0.2) + employment (0.1) + written_off (0.2) + loan_amount (0.1) = 1.0
        # Expected risk score: (0.6 / 1.0) * 100 = 60.0%
        profile_input = {
            "customer_id": "C001",
            "age": 65,
            "cibil_score": 620,
            "monthly_income": 50000,
            "existing_emis": 30000,
            "foir": 0.6,
            "employment_type": "salaried",
            "written_off_accounts": 0,
            "requested_amount": 200000
        }
        res = run_eligibility_evaluation(self.rules, profile_input)
        self.assertFalse(res["eligible"])
        self.assertIn("age", res["fail_reasons"])
        self.assertIn("cibil_score", res["fail_reasons"])
        self.assertIn("foir", res["fail_reasons"])
        self.assertEqual(res["risk_score"], 60.0)
        self.assertIn("Improve CIBIL score by at least 30 points", res["next_step"])

    def test_missing_field_in_input(self):
        """
        Test Case 6: Verify key error is caught and handled when field is missing.
        """
        # Missing credit_utilisation_pct for gap analysis
        report_input = {
            "customer_id": "C001",
            "missed_payments_12m": 2
        }
        with self.assertRaises(KeyError):
            run_gap_analysis(self.rules, report_input)

        # Missing age for eligibility
        profile_input = {
            "customer_id": "C001",
            "cibil_score": 620
        }
        with self.assertRaises(KeyError):
            run_eligibility_evaluation(self.rules, profile_input)

if __name__ == '__main__':
    unittest.main()
