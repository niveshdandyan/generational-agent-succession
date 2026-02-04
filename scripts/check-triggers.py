#!/usr/bin/env python3
"""
GAS Trigger Evaluator
Check if current generation should hand off to next generation.

Usage: python3 check-triggers.py <gas-dir> [generation-number]

Returns exit code:
  0 - No succession needed
  1 - Succession recommended (score > 0.50)
  2 - Succession urgent (score > 0.70)
  3 - Error reading status
"""

import sys
import json
import os
from datetime import datetime

# Default trigger weights
WEIGHTS = {
    'interactions': 0.25,
    'confidence': 0.30,
    'errors': 0.25,
    'stall': 0.20
}

# Default thresholds
THRESHOLDS = {
    'interaction_limit': 150,
    'confidence_min': 0.70,
    'error_rate_max': 0.15,
    'stall_minutes': 10
}


def read_json(path):
    """Read JSON file safely."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return None


def evaluate_triggers(status):
    """
    Evaluate succession triggers.
    Returns (should_handoff, urgency, reason, scores)
    """
    scores = {}

    # Interaction count trigger
    interactions = status.get('interactions', 0)
    scores['interactions'] = min(interactions / THRESHOLDS['interaction_limit'], 1.0)

    # Confidence trigger (inverted - lower confidence = higher score)
    confidence = status.get('confidence', 1.0)
    scores['confidence'] = max(0, 1 - (confidence / THRESHOLDS['confidence_min']))

    # Error rate trigger
    errors = status.get('errors', 0)
    total_actions = max(interactions, 1)
    error_rate = errors / total_actions
    scores['errors'] = min(error_rate / THRESHOLDS['error_rate_max'], 1.0)

    # Stall detection (if last_updated is old)
    stall_score = 0
    last_updated = status.get('last_updated')
    if last_updated:
        try:
            last_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            now = datetime.utcnow().replace(tzinfo=last_time.tzinfo)
            stall_minutes = (now - last_time).total_seconds() / 60
            stall_score = min(stall_minutes / THRESHOLDS['stall_minutes'], 1.0)
        except:
            pass
    scores['stall'] = stall_score

    # Calculate weighted composite score
    weighted_score = sum(scores[k] * WEIGHTS[k] for k in scores)

    # Determine urgency
    if weighted_score > 0.70:
        urgency = 'immediate'
        should_handoff = True
    elif weighted_score > 0.50:
        urgency = 'soon'
        should_handoff = True
    else:
        urgency = 'none'
        should_handoff = False

    # Find primary trigger
    primary_trigger = max(scores, key=scores.get)

    return should_handoff, urgency, primary_trigger, scores, weighted_score


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check-triggers.py <gas-dir> [generation-number]")
        sys.exit(3)

    gas_dir = sys.argv[1]
    gen_num = int(sys.argv[2]) if len(sys.argv) > 2 else None

    # If no generation specified, read current from state
    if gen_num is None:
        state = read_json(os.path.join(gas_dir, 'gas-state.json'))
        if state:
            gen_num = state.get('current_generation', 1)
        else:
            gen_num = 1

    # Read generation status
    status_path = os.path.join(gas_dir, 'generations', f'gen-{gen_num}', 'status.json')
    status = read_json(status_path)

    if not status:
        print(f"Could not read status for generation {gen_num}")
        sys.exit(3)

    # Check if already completed or failed
    if status.get('status') in ['completed', 'failed', 'needs_succession']:
        print(f"Generation {gen_num} already {status.get('status')}")
        sys.exit(0 if status.get('status') == 'completed' else 2)

    # Evaluate triggers
    should_handoff, urgency, primary_trigger, scores, weighted_score = evaluate_triggers(status)

    # Output results
    print("=" * 50)
    print(f"GAS Trigger Evaluation - Generation {gen_num}")
    print("=" * 50)
    print(f"Weighted Score: {weighted_score:.2f}")
    print(f"Should Handoff: {should_handoff}")
    print(f"Urgency: {urgency}")
    print(f"Primary Trigger: {primary_trigger}")
    print("-" * 50)
    print("Individual Scores:")
    for trigger, score in scores.items():
        weight = WEIGHTS[trigger]
        contribution = score * weight
        print(f"  {trigger:15} = {score:.2f} (weight {weight:.2f}, contrib {contribution:.2f})")
    print("=" * 50)

    # JSON output for programmatic use
    result = {
        'generation': gen_num,
        'weighted_score': weighted_score,
        'should_handoff': should_handoff,
        'urgency': urgency,
        'primary_trigger': primary_trigger,
        'scores': scores
    }
    print("\nJSON Output:")
    print(json.dumps(result, indent=2))

    # Exit code based on urgency
    if urgency == 'immediate':
        sys.exit(2)
    elif urgency == 'soon':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
