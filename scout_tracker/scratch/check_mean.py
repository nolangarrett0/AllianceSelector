import os
import sys
import json
import math

class TrueSkillRating:
    def __init__(self, mu=25.0, sigma=8.333):
        self.mu = mu
        self.sigma = sigma

def update_trueskill(winner_ratings, loser_ratings, margin=0):
    beta = 4.1667
    winner_mu = sum(r.mu for r in winner_ratings) / len(winner_ratings)
    winner_sigma = sum(r.sigma**2 for r in winner_ratings)**0.5 / len(winner_ratings)
    loser_mu = sum(r.mu for r in loser_ratings) / len(loser_ratings)
    loser_sigma = sum(r.sigma**2 for r in loser_ratings)**0.5 / len(loser_ratings)
    c = (2 * beta**2 + winner_sigma**2 + loser_sigma**2)**0.5
    t = (winner_mu - loser_mu) / c
    v = math.exp(-t**2 / 2) / (0.5 * (1 + math.erf(t / 2**0.5)) * (2 * math.pi)**0.5 + 0.001)
    w = v * (v + t)
    margin_factor = 1 + min(margin / 50, 0.5)
    for r in winner_ratings:
        r.mu += (r.sigma**2 / c) * v * margin_factor
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    for r in loser_ratings:
        r.mu -= (r.sigma**2 / c) * v * margin_factor
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)

EVENT_ID = 64025
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_HISTORY_FILE = os.path.join(root, "match_predictor", "cache", "season_history.json")

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f: return json.load(f)
    return {}

def _parse_match(match):
    alliances = match.get('alliances', [])
    alliance_dict = {a.get('color'): a for a in alliances} if isinstance(alliances, list) else alliances
    red_alliance = alliance_dict.get('red', {})
    blue_alliance = alliance_dict.get('blue', {})
    red_teams = [t['team']['name'] for t in red_alliance.get('teams', [])]
    blue_teams = [t['team']['name'] for t in blue_alliance.get('teams', [])]
    red_score = int(red_alliance.get('score', 0))
    blue_score = int(blue_alliance.get('score', 0))
    return red_teams, blue_teams, red_score, blue_score

def check_mean():
    ratings = {}
    history = load_json(SEASON_HISTORY_FILE)
    match_dict = {}
    for team, t_matches in history.items():
        for m in t_matches:
            key = f"{m.get('event_id', 0)}_{m['name']}"
            if key not in match_dict: match_dict[key] = m
    
    pre_worlds = []
    for key, m in match_dict.items():
        if m.get('event_id') != EVENT_ID:
            pre_worlds.append((m.get('started', "2000-01-01T00:00:00Z"), m))
    
    pre_worlds.sort(key=lambda x: x[0])
    for started, match in pre_worlds:
        rt, bt, rs, bs = _parse_match(match)
        for t in rt + bt:
            if t not in ratings: ratings[t] = TrueSkillRating()
        if rs == 0 and bs == 0: continue
        r_rats = [ratings[t] for t in rt if t in ratings]
        b_rats = [ratings[t] for t in bt if t in ratings]
        if not r_rats or not b_rats: continue
        if rs > bs: update_trueskill(r_rats, b_rats, abs(rs-bs))
        elif bs > rs: update_trueskill(b_rats, r_rats, abs(rs-bs))
    
    if not ratings:
        print("No ratings generated in Phase 1.")
        return

    global_mean = sum(r.mu for r in ratings.values()) / len(ratings)
    print(f"Phase 1 complete. Teams processed: {len(ratings)}")
    print(f"Global Mean mu: {global_mean:.2f} (PR: {global_mean*2:.1f})")
    
    # Check 84841Z specifically
    if "84841Z" in ratings:
        r = ratings["84841Z"]
        print(f"84841Z Phase 1 rating: mu={r.mu:.2f}, PR={r.mu*2:.1f}")
    else:
        print("84841Z not in Phase 1 results.")

if __name__ == "__main__":
    check_mean()
