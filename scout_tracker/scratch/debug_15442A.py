import json
import os
import sys

# Add parent directory to path to import from vex_scout_v11
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scout_tracker import calculate_ratings, fetch_all_matches

def debug_team(team_number):
    live_matches = fetch_all_matches()
    ratings = calculate_ratings(live_matches)
    print(f"Team {team_number} Power Rating: {ratings.get(team_number, 'N/A')}")
    
    # Let's see how many matches they have in season history
    season_history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "match_predictor", "cache", "season_history.json")
    with open(season_history_file, 'r') as f:
        history = json.load(f)
    
    matches = history.get(team_number, [])
    print(f"Found {len(matches)} matches in season history for {team_number}")
    
    # Check for duplicates in history itself
    keys = set()
    for m in matches:
        keys.add(f"{m.get('event_id')}_{m['name']}")
    print(f"Unique matches in history: {len(keys)}")

if __name__ == "__main__":
    debug_team("15442A")
