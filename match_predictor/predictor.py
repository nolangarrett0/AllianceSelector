import os
import sys
import json
import time
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add parent directory to path to import from vex_scout_v11
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from vex_scout_v11 import API_KEY, safe_request, TrueSkillRating, update_trueskill
except ImportError as e:
    print(f"Error importing from vex_scout_v11: {e}")
    sys.exit(1)

app = Flask(__name__)
CORS(app)

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
SEASON_CACHE_FILE = os.path.join(CACHE_DIR, 'season_history.json')
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_unique_teams(matches):
    teams = set()
    for match in matches:
        teams.update(match['red'])
        teams.update(match['blue'])
    return list(teams)

def get_team_id(team_number):
    url = f"https://www.robotevents.com/api/v2/teams?number={team_number}"
    data = safe_request(url, HEADERS)
    if data and data.get('data'):
        # Usually there could be multiple programs, filter by V5RC if needed, but usually number is unique enough for our purposes or we take first active
        for t in data['data']:
            if t['program']['code'] == 'V5RC' or t['program']['code'] == 'VRC':
                return t['id']
        return data['data'][0]['id']
    return None

def fetch_season_history(teams):
    # Fetch all matches for these teams in the current season
    # V5RC 2025-2026 Push Back is season 197
    print("Fetching season history for unique teams. This might take a while...")
    season_id = 197
    history = {}
    
    # We will fetch team IDs first
    team_ids = {}
    for team in teams:
        tid = get_team_id(team)
        if tid:
            team_ids[team] = tid
            print(f"Found ID for {team}: {tid}")
        else:
            print(f"Could not find ID for {team}")
            
    for team, tid in team_ids.items():
        print(f"Fetching matches for {team}...")
        matches = []
        page = 1
        while True:
            # We fetch all matches for this team in the season
            url = f"https://www.robotevents.com/api/v2/teams/{tid}/matches?season[]={season_id}&per_page=250&page={page}"
            data = safe_request(url, HEADERS)
            if not data or not data.get('data'):
                break
            
            for m in data['data']:
                # only keep what we need to save space
                match_info = {
                    'event_id': m['event']['id'],
                    'name': m['name'],
                    'started': m.get('started'),
                    'alliances': m['alliances']
                }
                matches.append(match_info)
                
            if page >= data['meta']['last_page']:
                break
            page += 1
            
        history[team] = matches
    
    with open(SEASON_CACHE_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    return history

def fetch_live_event_data(event_id, division_id):
    # Fetch matches from the specific Worlds event and division
    print(f"Fetching live event data for event {event_id}, division {division_id}...")
    matches = []
    page = 1
    while True:
        url = f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{division_id}/matches?per_page=250&page={page}"
        data = safe_request(url, HEADERS)
        if not data or not data.get('data'):
            break
            
        for m in data['data']:
            match_info = {
                'event_id': event_id,
                'name': m['name'],
                'started': m.get('started'),
                'alliances': m['alliances']
            }
            matches.append(match_info)
            
        if page >= data['meta']['last_page']:
            break
        page += 1
    return matches

def calculate_ratings(season_history, live_matches):
    ratings = {}
    # Combine season history and live matches
    # We want to process them chronologically
    all_matches = []
    
    # We need to deduplicate matches because a live match might also be in the season history if it was recently cached
    seen_matches = set()
    
    # First, gather all matches
    for team, t_matches in season_history.items():
        for m in t_matches:
            # Create a unique key for the match
            match_key = f"{m['event_id']}_{m['name']}"
            if match_key not in seen_matches:
                seen_matches.add(match_key)
                # Assign a pseudo-date if started is missing, though we prefer started
                started = m.get('started')
                if not started:
                    started = "2000-01-01T00:00:00Z"
                all_matches.append((started, m))
                
    for m in live_matches:
        match_key = f"{m['event_id']}_{m['name']}"
        if match_key not in seen_matches:
            seen_matches.add(match_key)
            started = m.get('started')
            if not started:
                started = "2000-01-01T00:00:00Z"
            all_matches.append((started, m))
            
    # Sort chronologically
    all_matches.sort(key=lambda x: x[0])
    
    # Run TrueSkill
    # Identify unique teams to init ratings
    for started, match in all_matches:
        alliances = match.get('alliances', [])
        alliance_dict = {a.get('color'): a for a in alliances} if isinstance(alliances, list) else alliances
        
        red_alliance = alliance_dict.get('red', {})
        blue_alliance = alliance_dict.get('blue', {})
        
        red_teams = [t['team']['name'] for t in red_alliance.get('teams', [])]
        blue_teams = [t['team']['name'] for t in blue_alliance.get('teams', [])]
        
        red_score = red_alliance.get('score', 0)
        blue_score = blue_alliance.get('score', 0)
        
        # Initialize missing teams
        for t in red_teams + blue_teams:
            if t not in ratings:
                ratings[t] = TrueSkillRating()
                
        # If match hasn't been played, skip
        if red_score == 0 and blue_score == 0:
            continue
            
        r_ratings = [ratings[t] for t in red_teams]
        b_ratings = [ratings[t] for t in blue_teams]
        
        if not r_ratings or not b_ratings:
            continue
            
        # Update based on winner
        margin = abs(red_score - blue_score)
        if red_score > blue_score:
            update_trueskill(r_ratings, b_ratings, margin)
        elif blue_score > red_score:
            update_trueskill(b_ratings, r_ratings, margin)
            
    return ratings

@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    config = load_config()
    unique_teams = get_unique_teams(config['matches'])
    
    # Load or fetch season history
    if os.path.exists(SEASON_CACHE_FILE):
        with open(SEASON_CACHE_FILE, 'r') as f:
            season_history = json.load(f)
    else:
        season_history = fetch_season_history(unique_teams)
        
    # Fetch live Worlds data
    live_matches = fetch_live_event_data(config['worlds_event_id'], config['worlds_division_id'])
    
    # Calculate current ratings
    ratings = calculate_ratings(season_history, live_matches)
    
    predictions = []
    
    # Normalize mu to a 0-100 power rating scale for display purposes
    # A starting mu is 25. High tier is 35+.
    def to_power_rating(mu):
        # Scale: 25 -> 50, 40 -> 100
        val = (mu - 10) * 3.33
        return max(0, min(100, round(val, 1)))
        
    for match in config['matches']:
        r1, r2 = match['red'][0], match['red'][1]
        b1, b2 = match['blue'][0], match['blue'][1]
        
        r1_mu = ratings.get(r1, TrueSkillRating()).mu
        r2_mu = ratings.get(r2, TrueSkillRating()).mu
        b1_mu = ratings.get(b1, TrueSkillRating()).mu
        b2_mu = ratings.get(b2, TrueSkillRating()).mu
        
        red_power = r1_mu + r2_mu
        blue_power = b1_mu + b2_mu
        
        total_power = red_power + blue_power
        if total_power == 0: total_power = 1 # avoid div by zero
        
        red_conf = round((red_power / total_power) * 100)
        blue_conf = 100 - red_conf
        
        winner = "Red" if red_conf > 50 else "Blue" if blue_conf > 50 else "Tie"
        conf = max(red_conf, blue_conf)
        
        predictions.append({
            "match": match['name'],
            "time": match['time'],
            "red": match['red'],
            "blue": match['blue'],
            "winner": winner,
            "confidence": conf,
            "red_conf": red_conf,
            "blue_conf": blue_conf,
            "details": {
                "red_ratings": {
                    r1: to_power_rating(r1_mu),
                    r2: to_power_rating(r2_mu)
                },
                "blue_ratings": {
                    b1: to_power_rating(b1_mu),
                    b2: to_power_rating(b2_mu)
                },
                "explanation": f"Red Alliance combined TrueSkill mu is {red_power:.1f}. Blue Alliance combined TrueSkill mu is {blue_power:.1f}. " + 
                               (f"Red is favored by {red_power - blue_power:.1f} points." if winner == "Red" else f"Blue is favored by {blue_power - red_power:.1f} points.")
            }
        })
        
    return jsonify({
        "status": "success",
        "predictions": predictions
    })

if __name__ == '__main__':
    print("Match Predictor API running on http://127.0.0.1:5001")
    app.run(port=5001, debug=True)
