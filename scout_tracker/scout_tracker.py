import os
import sys
import json
import time
import math
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

EVENT_ID = 64025
DIVISION_ID = 7
OUR_TEAM_NUMBER = "8568A"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
NOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team_notes.json")
TRACKED_TEAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracked_teams.json")
SEASON_HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "match_predictor", "cache", "season_history.json")

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return {}
    return {}

def save_json(filepath, data):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

def get_match_number(match_name):
    """Extracts the number from a match name like 'Qualifier #12' or 'Q12'."""
    import re
    match = re.search(r'#?(\d+)', match_name)
    if match:
        return int(match.group(1))
    return 0

def fetch_all_matches():
    """Fetch all matches for the Spirit division."""
    matches = []
    page = 1
    while True:
        url = f"https://www.robotevents.com/api/v2/events/{EVENT_ID}/divisions/{DIVISION_ID}/matches?per_page=250&page={page}"
        data = safe_request(url, HEADERS)
        if not data or not data.get('data'):
            break
        
        for m in data['data']:
            # Predictor includes all rounds with scores
            match_info = {
                'event_id': EVENT_ID,
                'name': m['name'],
                'started': m.get('started'),
                'alliances': m['alliances'],
                'scheduled': m.get('scheduled')
            }
            matches.append(match_info)
        
        if page >= data['meta']['last_page']:
            break
        page += 1
    return matches

def _parse_match(match):
    """Extract teams and scores from a match's alliance data. (Verbatim from predictor.py)"""
    alliances = match.get('alliances', [])
    alliance_dict = {a.get('color'): a for a in alliances} if isinstance(alliances, list) else alliances
    
    red_alliance = alliance_dict.get('red', {})
    blue_alliance = alliance_dict.get('blue', {})
    
    red_teams = [t['team']['name'] for t in red_alliance.get('teams', [])]
    blue_teams = [t['team']['name'] for t in blue_alliance.get('teams', [])]
    
    red_score = red_alliance.get('score')
    red_score = int(red_score) if red_score is not None else 0
    blue_score = blue_alliance.get('score')
    blue_score = int(blue_score) if blue_score is not None else 0
    
    return red_teams, blue_teams, red_score, blue_score

def weighted_update_trueskill(winner_ratings, loser_ratings, margin=0, weight=1.0, teammate_protect=False):
    """Enhanced TrueSkill update with weighting and protection. (Verbatim from predictor.py)"""
    beta = 4.1667
    MAX_MU_CHANGE = 10
    
    winner_mu = sum(r.mu for r in winner_ratings) / len(winner_ratings)
    winner_sigma = sum(r.sigma**2 for r in winner_ratings)**0.5 / len(winner_ratings)
    loser_mu = sum(r.mu for r in loser_ratings) / len(loser_ratings)
    loser_sigma = sum(r.sigma**2 for r in loser_ratings)**0.5 / len(loser_ratings)
    
    c = (2 * beta**2 + winner_sigma**2 + loser_sigma**2)**0.5
    t = (winner_mu - loser_mu) / c
    
    v = math.exp(-t**2 / 2) / (0.5 * (1 + math.erf(t / 2**0.5)) * (2 * math.pi)**0.5 + 0.001)
    w = v * (v + t)
    
    margin_factor = 1 + min(margin / 50, 0.5)
    
    # Winners
    for r in winner_ratings:
        delta = (r.sigma**2 / c) * v * margin_factor * weight
        r.mu += min(delta, MAX_MU_CHANGE)
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    
    # Losers
    if teammate_protect and len(loser_ratings) == 2:
        for i, r in enumerate(loser_ratings):
            partner = loser_ratings[1 - i]
            partner_ratio = min(partner.mu / r.mu, 1.0) if r.mu > 1 else 1.0
            loss_factor = 0.4 + 0.6 * partner_ratio
            delta = (r.sigma**2 / c) * v * margin_factor * weight * loss_factor
            r.mu -= min(delta, MAX_MU_CHANGE)
            r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    else:
        for r in loser_ratings:
            delta = (r.sigma**2 / c) * v * margin_factor * weight
            r.mu -= min(delta, MAX_MU_CHANGE)
            r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)

def calculate_ratings(live_matches):
    """
    3-Phase TrueSkill logic matching match_predictor/predictor.py precisely.
    Fixes deduplication, chronological sorting, and explicit event-id splitting.
    """
    ratings = {}
    season_history = load_json(SEASON_HISTORY_FILE)
    
    # ── Deduplicate matches (live data overwrites stale cache) ──
    match_dict = {}
    
    # Phase 1 source (Season history)
    for team, t_matches in season_history.items():
        for m in t_matches:
            eid = m.get('event_id', 0)
            match_key = f"{eid}_{m['name']}"
            if match_key not in match_dict:
                match_dict[match_key] = m
                
    # Phase 3 source (Live data)
    for m in live_matches:
        match_key = f"{m['event_id']}_{m['name']}"
        match_dict[match_key] = m
    
    # Build chronological list and split into pre-Worlds vs Worlds
    pre_worlds_matches = []
    worlds_matches = []
    
    for match_key, m in match_dict.items():
        started = m.get('started')
        if not started:
            started = "2000-01-01T00:00:00Z"
        
        if m.get('event_id') == EVENT_ID:
            worlds_matches.append((started, m))
        else:
            pre_worlds_matches.append((started, m))
    
    # GLOBAL CHRONOLOGICAL SORT
    pre_worlds_matches.sort(key=lambda x: x[0])
    worlds_matches.sort(key=lambda x: x[0])
    
    # PHASE 1: Season History baseline
    for started, match in pre_worlds_matches:
        red_teams, blue_teams, red_score, blue_score = _parse_match(match)
        
        for t in red_teams + blue_teams:
            if t not in ratings:
                ratings[t] = TrueSkillRating()
        
        if red_score == 0 and blue_score == 0:
            continue
            
        r_rats = [ratings[t] for t in red_teams]
        b_rats = [ratings[t] for t in blue_teams]
        
        if not r_rats or not b_rats:
            continue
        
        margin = abs(red_score - blue_score)
        if red_score > blue_score:
            update_trueskill(r_rats, b_rats, margin)
        elif blue_score > red_score:
            update_trueskill(b_rats, r_rats, margin)

    # PHASE 2: Regression to mean before Worlds
    if ratings and worlds_matches:
        global_mean = sum(r.mu for r in ratings.values()) / len(ratings)
        for r in ratings.values():
            r.mu = r.mu * 0.65 + global_mean * 0.35
            r.sigma = min(r.sigma + 0.8, 6.0)

    # PHASE 3: Worlds Matches
    WORLDS_WEIGHT = 1.8
    for started, match in worlds_matches:
        red_teams, blue_teams, red_score, blue_score = _parse_match(match)
        
        for t in red_teams + blue_teams:
            if t not in ratings:
                ratings[t] = TrueSkillRating()
        
        if red_score == 0 and blue_score == 0:
            continue
            
        r_rats = [ratings[t] for t in red_teams]
        b_rats = [ratings[t] for t in blue_teams]
        
        margin = abs(red_score - blue_score)
        if red_score > blue_score:
            weighted_update_trueskill(r_rats, b_rats, margin, weight=WORLDS_WEIGHT, teammate_protect=True)
        elif blue_score > red_score:
            weighted_update_trueskill(b_rats, r_rats, margin, weight=WORLDS_WEIGHT, teammate_protect=True)
            
    return {
        team: {
            'rating': round(r.mu * 2, 1),
            'confidence': round(max(0, (1 - (r.sigma - 1.0) / (8.333 - 1.0)) * 100))
        }
        for team, r in ratings.items()
    }

@app.route('/api/notes', methods=['GET'])
def get_notes():
    return jsonify(load_json(NOTES_FILE))

@app.route('/api/notes', methods=['POST'])
def update_note():
    data = request.json
    team = data.get('team')
    note = data.get('note')
    if not team: return jsonify({'status': 'error', 'message': 'Team number required'}), 400
    
    notes = load_json(NOTES_FILE)
    if note and note.strip(): notes[team] = note
    elif team in notes: del notes[team]
    
    if save_json(NOTES_FILE, notes): return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Failed to save note'}), 500

@app.route('/api/tracked-teams', methods=['GET'])
def get_tracked_teams():
    data = load_json(TRACKED_TEAMS_FILE)
    return jsonify(data if isinstance(data, list) else [])

@app.route('/api/tracked-teams', methods=['POST'])
def update_tracked_teams():
    data = request.json
    teams = data.get('teams', [])
    if save_json(TRACKED_TEAMS_FILE, teams): return jsonify({'status': 'success', 'teams': teams})
    return jsonify({'status': 'error', 'message': 'Failed to save teams'}), 500

@app.route('/api/scout-data', methods=['GET'])
def get_scout_data():
    current_match = request.args.get('current_match', default=0, type=int)
    notes = load_json(NOTES_FILE)
    tracked_teams = load_json(TRACKED_TEAMS_FILE)
    if not isinstance(tracked_teams, list): tracked_teams = []
    
    live_matches = fetch_all_matches()
    ratings = calculate_ratings(live_matches)
    
    # 1. Our matches
    our_matches = []
    for m in live_matches:
        red_t, blue_t, _, _ = _parse_match(m)
        if OUR_TEAM_NUMBER in red_t or OUR_TEAM_NUMBER in blue_t:
            our_matches.append(m)
    
    # 2. Team encounters
    team_encounters = {}
    for m in our_matches:
        our_match_num = get_match_number(m['name'])
        red_t, blue_t, _, _ = _parse_match(m)
        is_our_red = OUR_TEAM_NUMBER in red_t
        
        alliances = [
            (red_t, "Partner" if is_our_red else "Opponent"),
            (blue_t, "Partner" if not is_our_red else "Opponent")
        ]
        
        for teams, rel in alliances:
            for t_name in teams:
                if t_name == OUR_TEAM_NUMBER: continue
                if t_name not in team_encounters: team_encounters[t_name] = []
                team_encounters[t_name].append({'match_num': our_match_num, 'relationship': rel})

    # 3. Active targets
    active_targets = {}
    for team, encounters in team_encounters.items():
        for enc in encounters:
            if enc['match_num'] >= current_match:
                active_targets[team] = {'our_match': enc['match_num'], 'relationship': enc['relationship']}
                break

    # 4. Watchlist
    watchlist = []
    for m in live_matches:
        match_num = get_match_number(m['name'])
        if match_num < current_match: continue
        
        red_t, blue_t, _, _ = _parse_match(m)
        teams_to_watch = []
        
        for teams, color in [(red_t, 'red'), (blue_t, 'blue')]:
            for t_name in teams:
                if t_name in active_targets and match_num < active_targets[t_name]['our_match']:
                    teams_to_watch.append({
                        'number': t_name, 'color': color, 
                        'relationship': active_targets[t_name]['relationship'],
                        'our_match': active_targets[t_name]['our_match'],
                        'confidence': ratings.get(t_name, {}).get('confidence', 0),
                        'has_notes': t_name in notes and bool(notes[t_name].strip())
                    })
        
        if teams_to_watch:
            watchlist.append({'match_num': match_num, 'name': m['name'], 'scheduled': m.get('scheduled'), 'teams': teams_to_watch})

    # 5. Tracked Teams
    tracked_data = []
    for team_number in tracked_teams:
        team_matches = []
        for m in live_matches:
            red_t, blue_t, rs, bs = _parse_match(m)
            found, partner, opponents, team_color = False, None, [], 'unknown'
            
            if team_number in red_t:
                found, team_color, partner, opponents = True, 'red', [t for t in red_t if t != team_number], blue_t
            elif team_number in blue_t:
                found, team_color, partner, opponents = True, 'blue', [t for t in blue_t if t != team_number], red_t
            
            if found:
                partner_name = partner[0] if partner else None
                team_matches.append({
                    'match_num': get_match_number(m['name']),
                    'name': m['name'],
                    'partner': {
                        'number': partner_name, 
                        'rating': ratings.get(partner_name, {}).get('rating', 50.0),
                        'confidence': ratings.get(partner_name, {}).get('confidence', 0),
                        'has_notes': partner_name in notes and bool(notes[partner_name].strip())
                    } if partner_name else None,
                    'opponents': [{
                        'number': t, 
                        'rating': ratings.get(t, {}).get('rating', 50.0),
                        'confidence': ratings.get(t, {}).get('confidence', 0),
                        'has_notes': t in notes and bool(notes[t].strip())
                    } for t in opponents],
                    'team_color': team_color, 'red_score': rs, 'blue_score': bs
                })
        team_info = ratings.get(team_number, {'rating': 50.0, 'confidence': 0})
        tracked_data.append({
            'team': team_number, 
            'rating': team_info['rating'],
            'confidence': team_info['confidence'],
            'matches': sorted(team_matches, key=lambda x: x['match_num'])
        })

    watchlist.sort(key=lambda x: x['match_num'])
    return jsonify({
        'status': 'success', 'our_team': OUR_TEAM_NUMBER, 'current_match': current_match,
        'our_schedule': [get_match_number(m['name']) for m in our_matches],
        'watchlist': watchlist, 'tracked_data': tracked_data, 'all_ratings': ratings
    })

if __name__ == '__main__':
    print(f"Spirit Scouting Tracker API running on http://127.0.0.1:5005")
    app.run(port=5005, debug=True)
