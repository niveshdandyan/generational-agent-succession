#!/usr/bin/env python3
"""
GAS Knowledge Store Manager
===========================
Manages the shared knowledge store for success patterns, anti-patterns, and domain insights.

Usage:
    python3 knowledge-store.py add --store <path> --type <type> --context <ctx> --pattern <pat>
    python3 knowledge-store.py query --store <path> --type <type> [--context <ctx>]
    python3 knowledge-store.py prune --store <path> [--min-confidence 0.6] [--max-age-days 30]
    python3 knowledge-store.py export --store <path> [--format json|yaml|markdown]
    python3 knowledge-store.py stats --store <path>
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CONFIG = {
    "max_success_patterns": 50,
    "max_anti_patterns": 25,
    "max_domain_knowledge": 100,
    "min_confidence": 0.60,
    "default_confidence": 0.75,
    "decay_rate": 0.10,  # Per generation without use
    "promotion_threshold": 3  # Occurrences before promoting confidence
}


# =============================================================================
# Utility Functions
# =============================================================================

def timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def read_store(path: Path) -> Dict:
    """Read knowledge store from file."""
    if not path.exists():
        return create_empty_store()
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {path}", file=sys.stderr)
        return create_empty_store()


def write_store(path: Path, store: Dict):
    """Write knowledge store to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(store, f, indent=2)


def create_empty_store() -> Dict:
    """Create an empty knowledge store."""
    return {
        "created": timestamp(),
        "last_updated": timestamp(),
        "generations_completed": 0,
        "success_patterns": [],
        "anti_patterns": [],
        "domain_knowledge": []
    }


def generate_id(content: str) -> str:
    """Generate a short ID from content."""
    return hashlib.md5(content.encode()).hexdigest()[:8]


# =============================================================================
# Pattern Operations
# =============================================================================

def add_pattern(store: Dict, pattern_type: str, context: str, pattern: str,
                confidence: float = None, source_gen: int = None,
                source_agent: str = None, evidence: str = None,
                impact: str = None) -> Dict:
    """
    Add a new pattern to the knowledge store.
    
    Args:
        store: The knowledge store dict
        pattern_type: One of 'success_pattern', 'anti_pattern', 'domain_knowledge'
        context: When this pattern applies
        pattern: The pattern content/insight
        confidence: Confidence score (0.0 to 1.0)
        source_gen: Source generation number
        source_agent: Source agent ID
        evidence: Evidence for success patterns
        impact: Impact description for anti-patterns
    
    Returns:
        The added pattern entry
    """
    if confidence is None:
        confidence = DEFAULT_CONFIG["default_confidence"]
    
    # Check for duplicates
    existing = find_similar_pattern(store, pattern_type, pattern)
    if existing:
        # Update existing pattern's confidence
        existing["occurrences"] = existing.get("occurrences", 1) + 1
        existing["last_seen"] = timestamp()
        if existing["occurrences"] >= DEFAULT_CONFIG["promotion_threshold"]:
            existing["confidence"] = min(1.0, existing["confidence"] + 0.05)
        store["last_updated"] = timestamp()
        return existing
    
    entry = {
        "id": generate_id(f"{context}:{pattern}"),
        "context": context,
        "pattern": pattern,
        "confidence": confidence,
        "added_at": timestamp(),
        "last_seen": timestamp(),
        "occurrences": 1,
        "source_generation": source_gen,
        "source_agent": source_agent
    }
    
    if pattern_type == "success_pattern":
        entry["evidence"] = evidence or "Observed to work well"
        store["success_patterns"].append(entry)
        # Enforce max limit
        if len(store["success_patterns"]) > DEFAULT_CONFIG["max_success_patterns"]:
            store["success_patterns"] = prune_by_confidence(
                store["success_patterns"], 
                DEFAULT_CONFIG["max_success_patterns"]
            )
    
    elif pattern_type == "anti_pattern":
        entry["impact"] = impact or "Caused issues"
        store["anti_patterns"].append(entry)
        if len(store["anti_patterns"]) > DEFAULT_CONFIG["max_anti_patterns"]:
            store["anti_patterns"] = prune_by_confidence(
                store["anti_patterns"], 
                DEFAULT_CONFIG["max_anti_patterns"]
            )
    
    elif pattern_type == "domain_knowledge":
        entry["category"] = context  # Use context as category for domain knowledge
        store["domain_knowledge"].append(entry)
        if len(store["domain_knowledge"]) > DEFAULT_CONFIG["max_domain_knowledge"]:
            store["domain_knowledge"] = prune_by_confidence(
                store["domain_knowledge"], 
                DEFAULT_CONFIG["max_domain_knowledge"]
            )
    
    store["last_updated"] = timestamp()
    return entry


def find_similar_pattern(store: Dict, pattern_type: str, pattern: str) -> Optional[Dict]:
    """Find a similar pattern in the store (simple substring matching)."""
    patterns = store.get(f"{pattern_type}s" if not pattern_type.endswith("s") else pattern_type, [])
    pattern_lower = pattern.lower()
    
    for p in patterns:
        existing = p.get("pattern", "").lower()
        # Check for high similarity (one contains the other or same)
        if existing == pattern_lower or existing in pattern_lower or pattern_lower in existing:
            return p
    
    return None


def query_patterns(store: Dict, pattern_type: str = None, 
                   context: str = None, min_confidence: float = None,
                   limit: int = 10) -> List[Dict]:
    """
    Query patterns from the knowledge store.
    
    Args:
        store: The knowledge store dict
        pattern_type: Filter by type (success_pattern, anti_pattern, domain_knowledge)
        context: Filter by context (substring match)
        min_confidence: Minimum confidence threshold
        limit: Maximum number of results
    
    Returns:
        List of matching patterns
    """
    results = []
    
    types_to_search = ["success_patterns", "anti_patterns", "domain_knowledge"]
    if pattern_type:
        if not pattern_type.endswith("s"):
            pattern_type += "s"
        types_to_search = [pattern_type]
    
    for ptype in types_to_search:
        patterns = store.get(ptype, [])
        
        for p in patterns:
            # Apply filters
            if context and context.lower() not in p.get("context", "").lower():
                continue
            
            if min_confidence and p.get("confidence", 0) < min_confidence:
                continue
            
            results.append({**p, "type": ptype.rstrip("s")})
    
    # Sort by confidence (highest first)
    results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    
    return results[:limit]


def prune_by_confidence(patterns: List[Dict], max_count: int) -> List[Dict]:
    """Keep only the highest confidence patterns up to max_count."""
    sorted_patterns = sorted(patterns, key=lambda x: x.get("confidence", 0), reverse=True)
    return sorted_patterns[:max_count]


def prune_patterns(store: Dict, min_confidence: float = None, 
                   max_age_days: int = None) -> Dict:
    """
    Prune patterns based on confidence and age.
    
    Args:
        store: The knowledge store dict
        min_confidence: Remove patterns below this confidence
        max_age_days: Remove patterns older than this many days
    
    Returns:
        Summary of pruning
    """
    if min_confidence is None:
        min_confidence = DEFAULT_CONFIG["min_confidence"]
    
    removed = {"success_patterns": 0, "anti_patterns": 0, "domain_knowledge": 0}
    cutoff_date = None
    
    if max_age_days:
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
    
    for pattern_type in ["success_patterns", "anti_patterns", "domain_knowledge"]:
        original_count = len(store.get(pattern_type, []))
        
        filtered = []
        for p in store.get(pattern_type, []):
            # Check confidence
            if p.get("confidence", 1.0) < min_confidence:
                continue
            
            # Check age
            if cutoff_date:
                last_seen = p.get("last_seen") or p.get("added_at")
                if last_seen:
                    try:
                        pattern_date = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                        if pattern_date.replace(tzinfo=None) < cutoff_date:
                            continue
                    except:
                        pass
            
            filtered.append(p)
        
        store[pattern_type] = filtered
        removed[pattern_type] = original_count - len(filtered)
    
    store["last_updated"] = timestamp()
    return removed


def decay_unused_patterns(store: Dict, current_generation: int) -> Dict:
    """Apply confidence decay to patterns not seen recently."""
    decay_rate = DEFAULT_CONFIG["decay_rate"]
    affected = {"success_patterns": 0, "anti_patterns": 0}
    
    for pattern_type in ["success_patterns", "anti_patterns"]:
        for p in store.get(pattern_type, []):
            source_gen = p.get("source_generation", 0)
            if source_gen and current_generation - source_gen > 2:
                # Pattern is old and hasn't been reinforced
                occurrences = p.get("occurrences", 1)
                if occurrences <= 1:
                    p["confidence"] = max(0.1, p.get("confidence", 1.0) - decay_rate)
                    affected[pattern_type] += 1
    
    store["last_updated"] = timestamp()
    return affected


# =============================================================================
# Export Functions
# =============================================================================

def export_to_json(store: Dict, limit_per_type: int = 10) -> str:
    """Export store to JSON string."""
    export_data = {
        "success_patterns": store.get("success_patterns", [])[:limit_per_type],
        "anti_patterns": store.get("anti_patterns", [])[:limit_per_type],
        "domain_knowledge": store.get("domain_knowledge", [])[:limit_per_type]
    }
    return json.dumps(export_data, indent=2)


def export_to_markdown(store: Dict, limit_per_type: int = 10) -> str:
    """Export store to Markdown format for injection into prompts."""
    lines = ["# Accumulated Knowledge\n"]
    
    lines.append("## Success Patterns\n")
    patterns = store.get("success_patterns", [])[:limit_per_type]
    if patterns:
        for p in patterns:
            lines.append(f"- **{p.get('context', 'General')}**: {p.get('pattern', 'N/A')}")
            lines.append(f"  - Confidence: {p.get('confidence', 0):.0%}")
    else:
        lines.append("*No success patterns recorded yet.*")
    
    lines.append("\n## Anti-Patterns (Avoid These)\n")
    patterns = store.get("anti_patterns", [])[:limit_per_type]
    if patterns:
        for p in patterns:
            lines.append(f"- **{p.get('context', 'General')}**: {p.get('pattern', 'N/A')}")
            lines.append(f"  - Impact: {p.get('impact', 'Unknown')}")
    else:
        lines.append("*No anti-patterns recorded yet.*")
    
    lines.append("\n## Domain Insights\n")
    insights = store.get("domain_knowledge", [])[:limit_per_type]
    if insights:
        for p in insights:
            lines.append(f"- **{p.get('context', p.get('category', 'General'))}**: {p.get('pattern', 'N/A')}")
    else:
        lines.append("*No domain insights recorded yet.*")
    
    return "\n".join(lines)


def get_stats(store: Dict) -> Dict:
    """Get statistics about the knowledge store."""
    def avg_confidence(patterns):
        if not patterns:
            return 0
        return sum(p.get("confidence", 0) for p in patterns) / len(patterns)
    
    return {
        "success_patterns": {
            "count": len(store.get("success_patterns", [])),
            "avg_confidence": avg_confidence(store.get("success_patterns", []))
        },
        "anti_patterns": {
            "count": len(store.get("anti_patterns", [])),
            "avg_confidence": avg_confidence(store.get("anti_patterns", []))
        },
        "domain_knowledge": {
            "count": len(store.get("domain_knowledge", []))
        },
        "generations_completed": store.get("generations_completed", 0),
        "last_updated": store.get("last_updated", "Never")
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GAS Knowledge Store Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add a success pattern
  python3 knowledge-store.py add --store /workspace/project-gas/knowledge/store.json \\
    --type success_pattern --context "API design" --pattern "Use async/await for all DB queries"
  
  # Query patterns
  python3 knowledge-store.py query --store /workspace/project-gas/knowledge/store.json \\
    --type success_pattern --context "API"
  
  # Prune low-confidence patterns
  python3 knowledge-store.py prune --store /workspace/project-gas/knowledge/store.json \\
    --min-confidence 0.5
  
  # Export to markdown
  python3 knowledge-store.py export --store /workspace/project-gas/knowledge/store.json \\
    --format markdown
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # add command
    add_parser = subparsers.add_parser("add", help="Add a pattern to the store")
    add_parser.add_argument("--store", required=True, help="Path to knowledge store JSON")
    add_parser.add_argument("--type", required=True, 
                           choices=["success_pattern", "anti_pattern", "domain_knowledge"],
                           help="Type of pattern")
    add_parser.add_argument("--context", required=True, help="When this pattern applies")
    add_parser.add_argument("--pattern", required=True, help="The pattern or insight")
    add_parser.add_argument("--confidence", type=float, default=0.75, 
                           help="Confidence score (0.0-1.0)")
    add_parser.add_argument("--generation", type=int, help="Source generation number")
    add_parser.add_argument("--agent", help="Source agent ID")
    add_parser.add_argument("--evidence", help="Evidence (for success patterns)")
    add_parser.add_argument("--impact", help="Impact description (for anti-patterns)")
    
    # query command
    query_parser = subparsers.add_parser("query", help="Query patterns from the store")
    query_parser.add_argument("--store", required=True, help="Path to knowledge store JSON")
    query_parser.add_argument("--type", choices=["success_pattern", "anti_pattern", "domain_knowledge"],
                             help="Filter by type")
    query_parser.add_argument("--context", help="Filter by context (substring match)")
    query_parser.add_argument("--min-confidence", type=float, help="Minimum confidence")
    query_parser.add_argument("--limit", type=int, default=10, help="Maximum results")
    
    # prune command
    prune_parser = subparsers.add_parser("prune", help="Prune patterns from the store")
    prune_parser.add_argument("--store", required=True, help="Path to knowledge store JSON")
    prune_parser.add_argument("--min-confidence", type=float, default=0.5,
                             help="Remove patterns below this confidence")
    prune_parser.add_argument("--max-age-days", type=int,
                             help="Remove patterns older than this many days")
    
    # export command
    export_parser = subparsers.add_parser("export", help="Export the knowledge store")
    export_parser.add_argument("--store", required=True, help="Path to knowledge store JSON")
    export_parser.add_argument("--format", choices=["json", "markdown"], default="json",
                              help="Export format")
    export_parser.add_argument("--limit", type=int, default=10,
                              help="Limit per pattern type")
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Get statistics about the store")
    stats_parser.add_argument("--store", required=True, help="Path to knowledge store JSON")
    
    args = parser.parse_args()
    
    if args.command == "add":
        store = read_store(Path(args.store))
        entry = add_pattern(
            store=store,
            pattern_type=args.type,
            context=args.context,
            pattern=args.pattern,
            confidence=args.confidence,
            source_gen=args.generation,
            source_agent=args.agent,
            evidence=args.evidence,
            impact=args.impact
        )
        write_store(Path(args.store), store)
        print(f"Added pattern: {json.dumps(entry, indent=2)}")
    
    elif args.command == "query":
        store = read_store(Path(args.store))
        results = query_patterns(
            store=store,
            pattern_type=args.type,
            context=args.context,
            min_confidence=args.min_confidence,
            limit=args.limit
        )
        print(json.dumps(results, indent=2))
    
    elif args.command == "prune":
        store = read_store(Path(args.store))
        removed = prune_patterns(
            store=store,
            min_confidence=args.min_confidence,
            max_age_days=args.max_age_days
        )
        write_store(Path(args.store), store)
        print(f"Pruned patterns: {json.dumps(removed, indent=2)}")
    
    elif args.command == "export":
        store = read_store(Path(args.store))
        if args.format == "json":
            print(export_to_json(store, args.limit))
        else:
            print(export_to_markdown(store, args.limit))
    
    elif args.command == "stats":
        store = read_store(Path(args.store))
        stats = get_stats(store)
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
