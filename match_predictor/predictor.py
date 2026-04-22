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

def weighted_update_trueskill(winner_ratings, loser_ratings, margin=0, weight=1.0,
                               teammate_protect=False):
    """
    Enhanced TrueSkill update with event-importance weighting and teammate protection.
    
    Based on the core TrueSkill math from vex_scout_v11.update_trueskill, but extended
    with two key features for Worlds-level prediction:
    
    Parameters:
        winner_ratings (list): TrueSkillRating objects for winning alliance
        loser_ratings (list): TrueSkillRating objects for losing alliance
        margin (int): Point differential (bigger wins = bigger rating changes)
        weight (float): Multiplier for update magnitude.
                        >1.0 = stronger update (Worlds matches)
                        <1.0 = weaker update (old season matches)
        teammate_protect (bool): If True, reduce loss penalty for teams whose
                                  partner was significantly weaker. Prevents a
                                  good team from getting tanked by a bad random partner.
    """
    beta = 4.1667
    # Safety cap: no single match can move a team's mu by more than this amount.
    # Prevents a single blowout loss from destroying a team's rating entirely.
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
    
    # Update winners — full weighted reward, capped at MAX_MU_CHANGE
    for r in winner_ratings:
        delta = (r.sigma**2 / c) * v * margin_factor * weight
        r.mu += min(delta, MAX_MU_CHANGE)
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    
    # Update losers — with optional per-team teammate protection
    if teammate_protect and len(loser_ratings) == 2:
        # In VEX 2v2: if your partner is much weaker, you're less responsible for the loss.
        # We compute a per-team loss factor based on how strong their partner was relative to them.
        #   partner_ratio = partner_mu / team_mu  (capped at 1.0)
        #   loss_factor = 0.4 + 0.6 * partner_ratio
        # 
        # Examples:
        #   Equal partners (mu 30 + mu 30): ratio=1.0, loss_factor=1.0 → full penalty
        #   Weak partner  (mu 40 + mu 15): ratio=0.375, loss_factor=0.625 → ~63% penalty for the strong team
        #   Slightly weak (mu 30 + mu 25): ratio=0.833, loss_factor=0.9 → ~90% penalty
        for i, r in enumerate(loser_ratings):
            partner = loser_ratings[1 - i]
            if r.mu > 1:
                partner_ratio = min(partner.mu / r.mu, 1.0)
            else:
                partner_ratio = 1.0
            loss_factor = 0.4 + 0.6 * partner_ratio
            delta = (r.sigma**2 / c) * v * margin_factor * weight * loss_factor
            r.mu -= min(delta, MAX_MU_CHANGE)
            r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    else:
        # Standard update (no protection) — used for season history
        for r in loser_ratings:
            delta = (r.sigma**2 / c) * v * margin_factor * weight
            r.mu -= min(delta, MAX_MU_CHANGE)
            r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)


def _parse_match(match):
    """Extract teams and scores from a match's alliance data."""
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


def calculate_ratings(season_history, live_matches):
    """
    Calculate TrueSkill ratings in 3 phases to properly weight Worlds performance.
    
    The problem: A team dominating a weak regional event (e.g., Romania) builds a
    TrueSkill of 80, but at Worlds they'd be average. If we treat all matches equally,
    the season history drowns out Worlds performance and predictions never update.
    
    The solution — 3-phase processing:
    
    PHASE 1 (Baseline): Process season history to establish initial ratings.
            These matter, but represent a different competitive context.
    
    PHASE 2 (Regression): Before Worlds, regress all ratings toward the global mean.
            This prevents regional inflation from distorting Worlds predictions.
            A team rated 80 from dominating a weak field gets pulled down to ~55-60.
    
    PHASE 3 (Worlds): Process Worlds matches with HEAVY weighting (1.8x) and
            teammate-aware loss dampening. Worlds matches reflect current form at
            the highest level, so they should quickly override season baselines.
            Teammate protection ensures a good team with a bad random partner
            doesn't get unfairly punished.
    """
    config = load_config()
    worlds_event_id = config.get('worlds_event_id')
    
    ratings = {}
    
    # ── Deduplicate matches (live data overwrites stale cache) ──
    match_dict = {}
    
    for team, t_matches in season_history.items():
        for m in t_matches:
            match_key = f"{m['event_id']}_{m['name']}"
            if match_key not in match_dict:
                match_dict[match_key] = m
                
    # Live matches ALWAYS overwrite cached versions (fixes the stale-score bug)
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
        
        if m.get('event_id') == worlds_event_id:
            worlds_matches.append((started, m))
        else:
            pre_worlds_matches.append((started, m))
    
    pre_worlds_matches.sort(key=lambda x: x[0])
    worlds_matches.sort(key=lambda x: x[0])
    
    # ══════════════════════════════════════════════════════════════
    # PHASE 1: Season history baseline
    # Process all pre-Worlds matches to build initial ratings.
    # These establish the "prior" for each team — their historical form.
    # ══════════════════════════════════════════════════════════════
    for started, match in pre_worlds_matches:
        red_teams, blue_teams, red_score, blue_score = _parse_match(match)
        
        for t in red_teams + blue_teams:
            if t not in ratings:
                ratings[t] = TrueSkillRating()
        
        if red_score == 0 and blue_score == 0:
            continue
            
        r_ratings = [ratings[t] for t in red_teams]
        b_ratings = [ratings[t] for t in blue_teams]
        
        if not r_ratings or not b_ratings:
            continue
        
        margin = abs(red_score - blue_score)
        if red_score > blue_score:
            # Standard weight for season matches (using imported update_trueskill)
            update_trueskill(r_ratings, b_ratings, margin)
        elif blue_score > red_score:
            update_trueskill(b_ratings, r_ratings, margin)
    
    # ══════════════════════════════════════════════════════════════
    # PHASE 2: Regression to mean before Worlds
    # A team that was an 80 from dominating a weak regional field should NOT
    # carry that full advantage into Worlds. We regress everyone toward the
    # global mean to represent the uncertainty of a new competitive context.
    #
    # This is inspired by the same concept in sports analytics (e.g., baseball
    # preseason projections regress toward league average).
    # ══════════════════════════════════════════════════════════════
    if ratings and worlds_matches:
        global_mean = sum(r.mu for r in ratings.values()) / len(ratings)
        for team, r in ratings.items():
            # Pull 35% toward the global mean
            # A team at 80 with a global mean of 30 becomes: 80*0.65 + 30*0.35 = 62.5
            # A team at 30 stays roughly at: 30*0.65 + 30*0.35 = 30
            r.mu = r.mu * 0.65 + global_mean * 0.35
            
            # Increase uncertainty slightly — we're less sure how season form translates
            # to Worlds. A moderate bump (0.8) makes the system responsive to Worlds results
            # without letting a single match cause extreme rating swings.
            r.sigma = min(r.sigma + 0.8, 6.0)
    
    # ══════════════════════════════════════════════════════════════
    # PHASE 3: Worlds matches — heavily weighted with teammate protection
    # These are the matches that ACTUALLY matter for predictions.
    # - Weight = 1.8x (Worlds results override season baselines quickly)
    # - Teammate protection ON (don't punish a good team for having a bad
    #   random partner — this is qual matches, partners are assigned randomly)
    # ══════════════════════════════════════════════════════════════
    WORLDS_WEIGHT = 1.8  # 80% stronger updates than normal season matches
    
    for started, match in worlds_matches:
        red_teams, blue_teams, red_score, blue_score = _parse_match(match)
        
        for t in red_teams + blue_teams:
            if t not in ratings:
                ratings[t] = TrueSkillRating()
        
        if red_score == 0 and blue_score == 0:
            continue
            
        r_ratings = [ratings[t] for t in red_teams]
        b_ratings = [ratings[t] for t in blue_teams]
        
        if not r_ratings or not b_ratings:
            continue
        
        margin = abs(red_score - blue_score)
        if red_score > blue_score:
            weighted_update_trueskill(r_ratings, b_ratings, margin,
                                      weight=WORLDS_WEIGHT, teammate_protect=True)
        elif blue_score > red_score:
            weighted_update_trueskill(b_ratings, r_ratings, margin,
                                      weight=WORLDS_WEIGHT, teammate_protect=True)
            
    return ratings

def normalize_match_name(name):
    """Normalize match names so config format ('P 2', 'Q 14') matches
    API format ('Practice 2', 'Qualifier #14', 'Qualifier 14').
    Returns a canonical key like 'P2', 'Q14', etc."""
    n = name.strip()
    # Replace full names with abbreviations
    n = n.replace('Practice', 'P').replace('Qualifier', 'Q').replace('Final', 'F')
    # Strip '#' and extra spaces, collapse to single-space, then remove spaces
    n = n.replace('#', '')
    # Remove all spaces to get a compact key like 'P2', 'Q14'
    n = ''.join(n.split())
    return n

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
        red_teams, blue_teams, red_score, blue_score = _parse_match(m)
        if red_score != 0 or blue_score != 0:
            played_matches.append(m['name'])
            
    if played_matches:
        last_played = played_matches[-1]
        
    fetch_progress["status"] = "calculating"
    fetch_progress["detail"] = "Calculating TrueSkill predictions..."
    ratings = calculate_ratings(season_history, live_matches)
    
    predictions = []
    
    # ── Build a lookup of actual match results from live data ──
    # Keyed by normalized match name so we can cross-reference config names
    # (e.g. "Q 14") with API names (e.g. "Qualifier #14")
    live_results = {}
    for m in live_matches:
        red_teams, blue_teams, red_score, blue_score = _parse_match(m)
        is_played = (red_score != 0 or blue_score != 0)
        if is_played:
            if red_score > blue_score:
                actual_winner = "Red"
            elif blue_score > red_score:
                actual_winner = "Blue"
            else:
                actual_winner = "Tie"
            live_results[normalize_match_name(m['name'])] = {
                "red_score": red_score,
                "blue_score": blue_score,
                "actual_winner": actual_winner
            }
    
    def to_power_rating(mu):
        # Display-only: scale mu up 2x so numbers feel more substantial in the UI.
        # Does NOT affect predictions — those use raw mu internally.
        return round(mu * 2, 1)
    
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
        
        red_power_sum = to_power_rating(r1_r.mu) + to_power_rating(r2_r.mu)
        blue_power_sum = to_power_rating(b1_r.mu) + to_power_rating(b2_r.mu)
        
        prediction_data = {
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
                "explanation": f"Red Alliance combined Power Rating: {red_power_sum:.1f} (win prob {red_conf}%). Blue Alliance combined Power Rating: {blue_power_sum:.1f} (win prob {blue_conf}%). " + 
                               (f"Red is favored by {red_power_sum - blue_power_sum:.1f} rating points." if winner == "Red" else f"Blue is favored by {blue_power_sum - red_power_sum:.1f} rating points." if winner == "Blue" else "This match is essentially a coin flip.")
            }
        }
        
        # ── Attach actual results if this match has been played ──
        actual = live_results.get(normalize_match_name(match['name']))
        if actual:
            prediction_correct = (winner == actual['actual_winner']) or \
                                 (winner == "Toss-Up" and actual['actual_winner'] == "Tie")
            prediction_data["actual_result"] = {
                "played": True,
                "red_score": actual['red_score'],
                "blue_score": actual['blue_score'],
                "actual_winner": actual['actual_winner'],
                "prediction_correct": prediction_correct
            }
        else:
            prediction_data["actual_result"] = {"played": False}
        
        predictions.append(prediction_data)
        
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
