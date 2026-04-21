import os
import sys
import json
import math
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

fetch_progress = {"status": "idle", "percent": 0, "detail": ""}

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
    fetch_progress["status"] = "fetching_ids"
    for i, team in enumerate(teams):
        fetch_progress["detail"] = f"Finding Team ID for {team} ({i+1}/{len(teams)})"
        fetch_progress["percent"] = int((i / len(teams)) * 20)  # ID fetching is 20% of work
        tid = get_team_id(team)
        if tid:
            team_ids[team] = tid
            print(f"Found ID for {team}: {tid}")
        else:
            print(f"Could not find ID for {team}")
            
    fetch_progress["status"] = "fetching_matches"
    total_teams = len(team_ids)
    for i, (team, tid) in enumerate(team_ids.items()):
        fetch_progress["detail"] = f"Downloading season history for {team} ({i+1}/{total_teams})"
        fetch_progress["percent"] = 20 + int((i / total_teams) * 80)
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
    fetch_progress["status"] = "done"
    fetch_progress["percent"] = 100
    fetch_progress["detail"] = "Cache complete."
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
        
    fetch_progress["status"] = "live_data"
    fetch_progress["detail"] = "Fetching live Worlds data..."
    
    # Fetch live Worlds data
    live_matches = fetch_live_event_data(config['worlds_event_id'], config['worlds_division_id'])
    
    last_played = "None"
    played_matches = []
    for m in live_matches:
        if m.get('started'):
            played_matches.append(m['name'])
        else:
            alliances = m.get('alliances', [])
            alliance_dict = {a.get('color'): a for a in alliances} if isinstance(alliances, list) else alliances
            r_score = alliance_dict.get('red', {}).get('score', 0)
            b_score = alliance_dict.get('blue', {}).get('score', 0)
            if r_score != 0 or b_score != 0:
                played_matches.append(m['name'])
            
    if played_matches:
        last_played = played_matches[-1]
        
    fetch_progress["status"] = "calculating"
    fetch_progress["detail"] = "Calculating TrueSkill predictions..."
    ratings = calculate_ratings(season_history, live_matches)
    
    predictions = []
    
    # Collect all mu values for the teams in the schedule to build a percentile scale
    schedule_teams = get_unique_teams(config['matches'])
    schedule_mus = []
    for t in schedule_teams:
        r = ratings.get(t)
        if r:
            schedule_mus.append(r.mu)
    
    mu_min = min(schedule_mus) if schedule_mus else 15
    mu_max = max(schedule_mus) if schedule_mus else 50
    mu_range = mu_max - mu_min if mu_max > mu_min else 1
    
    def to_power_rating(mu):
        # Percentile-based: maps the lowest-rated schedule team to ~5
        # and the highest-rated to ~99, with everyone else spread between
        val = ((mu - mu_min) / mu_range) * 94 + 5
        return max(0, min(100, round(val, 1)))
    
    def win_probability(team_a_mus, team_a_sigmas, team_b_mus, team_b_sigmas):
        """
        Calculate the probability that alliance A beats alliance B using
        the TrueSkill Gaussian model. This accounts for both skill (mu)
        and uncertainty (sigma).
        """
        # We double the beta (randomness factor) for PREDICTIONS.
        # While 4.1667 is mathematically optimal for tracking true skill changes,
        # VEX matches have high "chaos" (disconnects, tipping, auto fails).
        # A higher beta flattens the curve, so a massive skill gap gives 
        # a realistic 85-90% confidence instead of an unrealistic 99-100%.
        prediction_beta = 4.1667 * 2.5 
        
        # Calculate average skill and combined uncertainty for each alliance
        a_mu = sum(team_a_mus) / len(team_a_mus)
        a_sigma = sum(s**2 for s in team_a_sigmas)**0.5 / len(team_a_sigmas)
        
        b_mu = sum(team_b_mus) / len(team_b_mus)
        b_sigma = sum(s**2 for s in team_b_sigmas)**0.5 / len(team_b_sigmas)
        
        # c is the total uncertainty in the match outcome (including game randomness beta)
        c = (2 * prediction_beta**2 + a_sigma**2 + b_sigma**2)**0.5
        
        # t is the normalized skill difference
        t = (a_mu - b_mu) / c
        
        # Use the cumulative normal distribution via math.erf
        prob = 0.5 * (1 + math.erf(t / 2**0.5))
        return prob
        
    for match in config['matches']:
        r1, r2 = match['red'][0], match['red'][1]
        b1, b2 = match['blue'][0], match['blue'][1]
        
        r1_r = ratings.get(r1, TrueSkillRating())
        r2_r = ratings.get(r2, TrueSkillRating())
        b1_r = ratings.get(b1, TrueSkillRating())
        b2_r = ratings.get(b2, TrueSkillRating())
        
        # Win probability using proper TrueSkill math
        red_win_prob = win_probability(
            [r1_r.mu, r2_r.mu], [r1_r.sigma, r2_r.sigma],
            [b1_r.mu, b2_r.mu], [b1_r.sigma, b2_r.sigma]
        )
        
        red_conf = round(red_win_prob * 100)
        blue_conf = 100 - red_conf
        
        winner = "Red" if red_conf > 50 else "Blue" if blue_conf > 50 else "Toss-Up"
        conf = max(red_conf, blue_conf)
        
        red_power_sum = r1_r.mu + r2_r.mu
        blue_power_sum = b1_r.mu + b2_r.mu
        
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
                    r1: to_power_rating(r1_r.mu),
                    r2: to_power_rating(r2_r.mu)
                },
                "blue_ratings": {
                    b1: to_power_rating(b1_r.mu),
                    b2: to_power_rating(b2_r.mu)
                },
                "explanation": f"Red Alliance combined TrueSkill: {red_power_sum:.1f} (win prob {red_conf}%). Blue Alliance combined TrueSkill: {blue_power_sum:.1f} (win prob {blue_conf}%). " + 
                               (f"Red is favored by {red_power_sum - blue_power_sum:.1f} skill points." if winner == "Red" else f"Blue is favored by {blue_power_sum - red_power_sum:.1f} skill points." if winner == "Blue" else "This match is essentially a coin flip.")
            }
        })
        
    fetch_progress["status"] = "idle"
    
    return jsonify({
        "status": "success",
        "last_played": last_played,
        "predictions": predictions
    })

@app.route('/api/progress', methods=['GET'])
def get_progress():
    return jsonify(fetch_progress)

if __name__ == '__main__':
    print("Match Predictor API running on http://127.0.0.1:5001")
    app.run(port=5001, debug=True)
