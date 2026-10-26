import json
import os
import sys
from typing import List, Dict, Any

APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
PROFILE_PATH = os.path.join(APP_DIR, "user_profile.json")

def load_profile() -> Dict[str, Any]:
    if not os.path.exists(PROFILE_PATH):
        return {"keyword_weights": {}, "history": []}
    
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"keyword_weights": {}, "history": []}

def save_profile(profile_data: Dict[str, Any]) -> None:
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)

def update_weights(keywords: List[str], rating: int) -> None:
    profile = load_profile()
    
    # Weight logic: adjustment = (rating - 3) * 0.1
    adjustment = (rating - 3) * 0.1
    
    for keyword in keywords:
        kw_lower = keyword.lower()
        current_weight = profile["keyword_weights"].get(kw_lower, 1.0)
        
        # We apply the adjustment
        new_weight = current_weight + adjustment
        
        # Ensure weights never go below 0.1
        if new_weight < 0.1:
            new_weight = 0.1
            
        profile["keyword_weights"][kw_lower] = new_weight
    
    profile["history"].append({
        "keywords": keywords,
        "rating": rating,
        "adjustment": adjustment
    })
    
    save_profile(profile)
