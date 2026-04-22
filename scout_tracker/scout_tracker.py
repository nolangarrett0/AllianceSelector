import os
import sys
import json
import time
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add parent directory to path to import from vex_scout_v11
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from vex_scout_v11 import API_KEY, safe_request
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

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading notes: {e}")
            return {}
    return {}

def save_notes(notes):
    try:
        with open(NOTES_FILE, 'w') as f:
            json.dump(notes, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving notes: {e}")
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
            # Only keep qualification matches for this specific tool
            if m.get('round') == 2:  # 2 is typically Qualifiers
                matches.append(m)
        
        if page >= data['meta']['last_page']:
            break
        page += 1
    return matches

@app.route('/api/notes', methods=['GET'])
def get_notes():
    return jsonify(load_notes())

@app.route('/api/notes', methods=['POST'])
def update_note():
    data = request.json
    team = data.get('team')
    note = data.get('note')
    
    if not team:
        return jsonify({'status': 'error', 'message': 'Team number required'}), 400
    
    notes = load_notes()
    if note and note.strip():
        notes[team] = note
    elif team in notes:
        del notes[team]
    
    if save_notes(notes):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to save note'}), 500

@app.route('/api/scout-data', methods=['GET'])
def get_scout_data():
    current_match = request.args.get('current_match', default=0, type=int)
    notes = load_notes()
    
    all_matches = fetch_all_matches()
    
    # 1. Find all matches our team is in
    our_matches = []
    for m in all_matches:
        teams_in_match = []
        for alliance in m.get('alliances', []):
            for t in alliance.get('teams', []):
                teams_in_match.append(t['team']['name'])
        
        if OUR_TEAM_NUMBER in teams_in_match:
            our_matches.append(m)
    
    # 2. Identify partners and opponents for each of our matches
    targets = {} # team_name -> { 'match_with_us': int, 'relationship': 'Partner'|'Opponent' }
    
    for m in our_matches:
        our_match_num = get_match_number(m['name'])
        
        for alliance in m.get('alliances', []):
            is_our_alliance = False
            for t in alliance.get('teams', []):
                if t['team']['name'] == OUR_TEAM_NUMBER:
                    is_our_alliance = True
                    break
            
            relationship = "Partner" if is_our_alliance else "Opponent"
            
            for t in alliance.get('teams', []):
                team_name = t['team']['name']
                if team_name == OUR_TEAM_NUMBER:
                    continue
                
                # If we play a team multiple times, prioritize the earliest one for scouting
                if team_name not in targets or our_match_num < targets[team_name]['match_with_us']:
                    targets[team_name] = {
                        'match_with_us': our_match_num,
                        'relationship': relationship
                    }

    # 3. Filter targets based on current_match
    # Remove teams we've already played with/against in ALL their matches with us
    active_targets = {}
    for team, info in targets.items():
        if info['match_with_us'] >= current_match:
            active_targets[team] = info

    # 4. Aggregate matches to watch
    watchlist = []
    for m in all_matches:
        match_num = get_match_number(m['name'])
        
        # Only show upcoming matches
        if match_num < current_match:
            continue
            
        # Check if any active target is in this match
        teams_to_watch = []
        for alliance in m.get('alliances', []):
            color = alliance.get('color', 'unknown')
            for t in alliance.get('teams', []):
                team_name = t['team']['name']
                if team_name in active_targets:
                    teams_to_watch.append({
                        'number': team_name,
                        'color': color,
                        'relationship': active_targets[team_name]['relationship'],
                        'our_match': active_targets[team_name]['match_with_us'],
                        'has_notes': team_name in notes and bool(notes[team_name].strip())
                    })
        
        if teams_to_watch:
            watchlist.append({
                'match_num': match_num,
                'name': m['name'],
                'scheduled': m.get('scheduled'),
                'teams': teams_to_watch
            })

    # Sort watchlist by match number
    watchlist.sort(key=lambda x: x['match_num'])

    return jsonify({
        'status': 'success',
        'our_team': OUR_TEAM_NUMBER,
        'current_match': current_match,
        'our_schedule': [get_match_number(m['name']) for m in our_matches],
        'watchlist': watchlist
    })

if __name__ == '__main__':
    print(f"Spirit Scouting Tracker API running on http://127.0.0.1:5005")
    app.run(port=5005, debug=True)
