import argparse
import json
import os
import sys
import yaml

def evaluate_operator(operator, value, rule_def, input_data):
    """
    Evaluates whether the value matches the rule definition condition.
    """
    if operator == 'gte':
        target = rule_def.get('value')
        if target is None:
            raise ValueError(f"Missing 'value' for operator 'gte' in rule definition")
        return value >= target, f"Value {value} is below required {target}"
    
    elif operator == 'lte':
        target = rule_def.get('value')
        if target is None:
            raise ValueError(f"Missing 'value' for operator 'lte' in rule definition")
        return value <= target, f"Value {value} exceeds limit of {target}"
    
    elif operator == 'gt':
        target = rule_def.get('value')
        if target is None:
            raise ValueError(f"Missing 'value' for operator 'gt' in rule definition")
        return value > target, f"Value {value} is not strictly greater than {target}"
    
    elif operator == 'lt':
        target = rule_def.get('value')
        if target is None:
            raise ValueError(f"Missing 'value' for operator 'lt' in rule definition")
        return value < target, f"Value {value} is not strictly less than {target}"
    
    elif operator == 'eq':
        target = rule_def.get('value')
        if target is None:
            raise ValueError(f"Missing 'value' for operator 'eq' in rule definition")
        return value == target, f"Value {value} is not equal to {target}"
    
    elif operator == 'between':
        min_val = rule_def.get('min')
        max_val = rule_def.get('max')
        if min_val is None or max_val is None:
            raise ValueError(f"Missing 'min' or 'max' for operator 'between' in rule definition")
        return min_val <= value <= max_val, f"Value {value} is not between {min_val} and {max_val}"
    
    elif operator == 'in':
        values = rule_def.get('values')
        if not isinstance(values, list):
            raise ValueError(f"Missing 'values' list for operator 'in' in rule definition")
        return value in values, f"Value {value} is not in allowed list {values}"
    
    elif operator == 'lte_multiplier':
        mult_field = rule_def.get('multiplier_field')
        mult_val = rule_def.get('multiplier')
        if not mult_field or mult_val is None:
            raise ValueError(f"Missing 'multiplier_field' or 'multiplier' for operator 'lte_multiplier' in rule definition")
        
        if mult_field not in input_data:
            raise KeyError(mult_field)
            
        limit = input_data[mult_field] * mult_val
        return value <= limit, f"Value {value} exceeds multiplier cap of {limit} ({mult_val}x {mult_field})"
    
    else:
        raise ValueError(f"Unsupported operator '{operator}'")

def run_gap_analysis(rules, input_data):
    """
    Evaluates credit gap rules and returns the list of triggered gaps.
    """
    customer_id = input_data.get('customer_id', 'UNKNOWN')
    gaps = []
    gap_rules = rules.get('gap_rules', [])
    
    for rule in gap_rules:
        field = rule.get('field')
        if not field:
            raise ValueError("Gap rule missing 'field' attribute")
            
        if field not in input_data:
            raise KeyError(field)
            
        val = input_data[field]
        operator = rule.get('operator')
        
        # In gap analysis, a gap fires if the condition evaluates to True.
        # e.g., credit_utilisation_pct > 30 => High Utilisation Gap fires
        fired, _ = evaluate_operator(operator, val, rule, input_data)
        
        if fired:
            action_template = rule.get('action_template', '')
            action = action_template.format(current_value=val)
            gaps.append({
                "id": rule.get('id'),
                "impact": rule.get('impact', 'low'),
                "estimated_score_gain": rule.get('estimated_score_gain', 0),
                "action": action
            })
            
    # Sort: high -> medium -> low, then by estimated_score_gain descending
    impact_rank = {'high': 1, 'medium': 2, 'low': 3}
    gaps.sort(key=lambda x: (impact_rank.get(x['impact'], 4), -x['estimated_score_gain']))
    
    total_gain = sum(g['estimated_score_gain'] for g in gaps)
    
    return {
        "customer_id": customer_id,
        "mode": "gap_analysis",
        "gaps_found": len(gaps),
        "total_potential_score_gain": total_gain,
        "gaps": gaps
    }

def run_eligibility_evaluation(rules, input_data):
    """
    Evaluates customer profile eligibility based on rules.yaml.
    """
    customer_id = input_data.get('customer_id', 'UNKNOWN')
    eligibility_groups = rules.get('eligibility_rules', [])
    
    if not eligibility_groups:
        return {
            "customer_id": customer_id,
            "mode": "eligibility",
            "eligible": True,
            "rules": [],
            "fail_reasons": [],
            "risk_score": 0.0,
            "next_step": "No rules configured. Eligible by default."
        }
        
    # We will evaluate each rule group. The primary output model structure is:
    # { "rule": id, "passed": bool, "reason": str }
    evaluated_rules = []
    fail_reasons = []
    
    # We will support a single group or multiple. Let's process the first rule group.
    group = eligibility_groups[0]
    logic_mode = group.get('logic', 'AND')
    group_rules = group.get('rules', [])
    
    total_weight = 0.0
    failed_weight = 0.0
    
    group_passed = True if logic_mode == 'AND' else False
    
    for rule in group_rules:
        field = rule.get('field')
        rule_id = rule.get('id')
        weight = rule.get('weight', 0.0)
        total_weight += weight
        
        if not field:
            raise ValueError(f"Eligibility rule {rule_id} is missing 'field'")
            
        if field not in input_data:
            raise KeyError(field)
            
        val = input_data[field]
        operator = rule.get('operator')
        
        # Evaluate if the rule passes. If passed is True, the customer meets the criteria.
        passed, fail_msg = evaluate_operator(operator, val, rule, input_data)
        
        rule_result = {
            "rule": rule_id,
            "passed": passed
        }
        
        if not passed:
            custom_msg = rule.get('message')
            rule_result["reason"] = custom_msg if custom_msg else fail_msg
            fail_reasons.append(rule_id)
            failed_weight += weight
            
        evaluated_rules.append(rule_result)
        
        if logic_mode == 'AND':
            if not passed:
                group_passed = False
        else: # OR
            if passed:
                group_passed = True
                
    # If group is OR and we passed, the overall is eligible.
    eligible = group_passed
    
    # Risk score calculation
    risk_score = 0.0
    if total_weight > 0:
        risk_score = (failed_weight / total_weight) * 100
        
    # Generate helper next step message
    next_step = "Proceed with loan disbursement."
    if not eligible:
        if "cibil_score" in fail_reasons:
            req_score = 650
            curr_score = input_data.get('cibil_score', 0)
            diff = max(0, req_score - curr_score)
            next_step = f"Improve CIBIL score by at least {diff} points. See gap analysis for details."
        elif "no_written_off_accounts" in fail_reasons:
            next_step = "Settle all written-off accounts with credit bureaus."
        elif "foir" in fail_reasons:
            next_step = "Reduce existing EMI obligations or show higher income to improve FOIR."
        else:
            next_step = "Review failed parameters and apply again."
            
    return {
        "customer_id": customer_id,
        "mode": "eligibility",
        "eligible": eligible,
        "rules": evaluated_rules,
        "fail_reasons": fail_reasons,
        "risk_score": round(risk_score, 2),
        "next_step": next_step
    }

def main():
    parser = argparse.ArgumentParser(description="Softlend Configurable Rule Engine")
    parser.add_argument('--mode', choices=['gap_analysis', 'eligibility'], required=True, help="Mode of the engine")
    parser.add_argument('--input', required=True, help="Path to input JSON file")
    parser.add_argument('--rules', default=None, help="Path to rules YAML file")
    
    args = parser.parse_args()
    
    # Find rules.yaml
    rules_path = args.rules
    if not rules_path:
        # Default path relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        rules_path = os.path.join(script_dir, 'rules.yaml')
        
    if not os.path.exists(rules_path):
        print(json.dumps({"error": f"Rules configuration not found at {rules_path}", "code": "CONFIG_NOT_FOUND"}))
        sys.exit(1)
        
    if not os.path.exists(args.input):
        print(json.dumps({"error": f"Input file not found at {args.input}", "code": "INPUT_NOT_FOUND"}))
        sys.exit(1)
        
    try:
        with open(rules_path, 'r') as f:
            rules = yaml.safe_load(f)
    except Exception as e:
        print(json.dumps({"error": f"Error parsing rules YAML: {str(e)}", "code": "INVALID_CONFIG"}))
        sys.exit(1)
        
    try:
        with open(args.input, 'r') as f:
            input_data = json.load(f)
    except Exception as e:
        print(json.dumps({"error": f"Error parsing input JSON: {str(e)}", "code": "INVALID_INPUT"}))
        sys.exit(1)
        
    try:
        if args.mode == 'gap_analysis':
            output = run_gap_analysis(rules, input_data)
        else:
            output = run_eligibility_evaluation(rules, input_data)
            
        print(json.dumps(output, indent=2))
        
    except KeyError as ke:
        print(json.dumps({
            "error": f"Missing required field in input: '{ke.args[0]}'",
            "code": "MISSING_INPUT_FIELD"
        }, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "error": f"Internal rule engine error: {str(e)}",
            "code": "RULE_ENGINE_ERROR"
        }, indent=2))
        sys.exit(1)

if __name__ == '__main__':
    main()
