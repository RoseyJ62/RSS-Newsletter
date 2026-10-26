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

# Each scale maps a rating to (label, description, weight adjustment per matched keyword).
# A rating can only change the weights of keywords that matched the article.
RATING_SCALES = {
    5: {
        1: ("Strongly dislike", "Show far fewer articles like this.", -0.2),
        2: ("Dislike", "Show somewhat fewer articles like this.", -0.1),
        3: ("Neutral", "No effect on future recommendations.", 0.0),
        4: ("Like", "Show somewhat more articles like this.", 0.1),
        5: ("Strongly like", "Show far more articles like this.", 0.2),
    },
}
CURRENT_RATING_SCALE = 5

def rating_adjustment(rating: int, scale: int = CURRENT_RATING_SCALE) -> float:
    return RATING_SCALES[scale][rating][2]

def update_weights(keywords: List[str], rating: int, scale: int = CURRENT_RATING_SCALE) -> None:
    profile = load_profile()
    
    adjustment = rating_adjustment(rating, scale)
    
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
        "scale": scale,
        "label": RATING_SCALES[scale][rating][0],
        "adjustment": adjustment
    })
    
    save_profile(profile)
