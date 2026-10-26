import json
import os
import re
import sys
from typing import Dict, Any, List

def _context_path():
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "osf_context.json")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "osf_context.json")

def load_context() -> Dict[str, Any]:
    with open(_context_path(), "r", encoding="utf-8") as f:
        return json.load(f)

def save_context(context: Dict[str, Any]):
    with open(_context_path(), "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

def score_article(article_title: str, article_summary: str, user_profile: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    if context is None:
        context = load_context()

    text_to_search = f"{article_title} {article_summary}".lower()
    
    keyword_rules = context.get("keyword_rules", {})
    high_signal_kws = [kw.lower() for kw in keyword_rules.get("high_signal", [])]
    low_signal_kws = [kw.lower() for kw in keyword_rules.get("low_signal", [])]
    low_signal_requires_pair = keyword_rules.get("low_signal_requires_pair", False)

    # First, find all raw matches
    raw_matches = set()
    
    # We will search all keywords defined in focus_areas, strategic_goals, and initiatives
    categories = [
        ("focus_areas", context.get("focus_areas", [])),
        ("strategic_goals", context.get("strategic_goals", [])),
        ("initiatives", context.get("initiatives", []))
    ]
    
    keyword_to_category = {}
    keyword_to_base_weight = {}
    
    for cat_key, cat_list in categories:
        for item in cat_list:
            base_w = item.get("weight", 1)
            cat_name = item.get("name", "Unknown")
            for kw in item.get("keywords", []):
                kw_lower = kw.lower()
                keyword_to_category[kw_lower] = cat_name
                keyword_to_base_weight[kw_lower] = base_w
                
                # Check for match using word boundaries
                pattern = r'\b' + re.escape(kw_lower) + r'\b'
                if re.search(pattern, text_to_search):
                    raw_matches.add(kw_lower)

    # Apply low signal rules
    has_high_signal = any(kw in raw_matches for kw in high_signal_kws)
    
    valid_matches = []
    for kw in raw_matches:
        if kw in low_signal_kws and low_signal_requires_pair:
            if not has_high_signal:
                continue # Skip this low signal keyword
        valid_matches.append(kw)

    total_score = 0.0
    matched_categories = set()
    user_weights = user_profile.get("keyword_weights", {})
    
    for kw in valid_matches:
        base_weight = keyword_to_base_weight.get(kw, 0)
        user_weight = user_weights.get(kw, 1.0)
        
        keyword_score = base_weight * user_weight
        total_score += keyword_score
        
        cat_name = keyword_to_category.get(kw)
        if cat_name:
            matched_categories.add(cat_name)

    explanation = "No specific strategic keywords matched."
    if valid_matches:
        explanation = f"Matched {len(valid_matches)} keywords: {', '.join(valid_matches)}. "
        if matched_categories:
            explanation += f"Categories: {', '.join(matched_categories)}."

    return {
        "score": total_score,
        "matched_keywords": valid_matches,
        "matched_categories": list(matched_categories),
        "explanation": explanation
    }
