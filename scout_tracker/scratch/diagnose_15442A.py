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
    for r in winner_ratings:
        r.mu += (r.sigma**2 / c) * v
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    for r in loser_ratings:
        r.mu -= (r.sigma**2 / c) * v
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)

def weighted_update_trueskill(winner_ratings, loser_ratings, margin=0, weight=1.0, teammate_protect=False):
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
    for r in winner_ratings:
        delta = (r.sigma**2 / c) * v * margin_factor * weight
        r.mu += min(delta, MAX_MU_CHANGE)
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
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

def diagnose(target_team):
    ratings = {}
    history = load_json(SEASON_HISTORY_FILE)
    match_dict = {}
    for team, t_matches in history.items():
        for m in t_matches:
            key = f"{m.get('event_id', 0)}_{m['name']}"
            if key not in match_dict: match_dict[key] = m
    pre_worlds = []
    worlds = []
    for key, m in match_dict.items():
        started = m.get('started', "2000-01-01T00:00:00Z")
        if m.get('event_id') == EVENT_ID: worlds.append((started, m))
        else: pre_worlds.append((started, m))
    pre_worlds.sort(key=lambda x: x[0])
    worlds.sort(key=lambda x: x[0])
    for started, match in pre_worlds:
        rt, bt, rs, bs = _parse_match(match)
        for t in rt + bt:
            if t not in ratings: ratings[t] = TrueSkillRating()
        if rs == 0 and bs == 0: continue
        r_rats = [ratings[t] for t in rt if t in ratings]
        b_rats = [ratings[t] for t in bt if t in ratings]
        if not r_rats or not b_rats: continue
        if rs > bs: update_trueskill(r_rats, b_rats)
        elif bs > rs: update_trueskill(b_rats, r_rats)
    if target_team in ratings: print(f"After Phase 1 (Season): {target_team} mu={ratings[target_team].mu:.2f}, PR={ratings[target_team].mu*2:.1f}")
    else: print(f"{target_team} NOT in history."); ratings[target_team] = TrueSkillRating()
    global_mean = sum(r.mu for r in ratings.values()) / len(ratings)
    for r in ratings.values():
        r.mu = r.mu * 0.65 + global_mean * 0.35
        r.sigma = min(r.sigma + 0.8, 6.0)
    print(f"After Phase 2 (Regression): {target_team} mu={ratings[target_team].mu:.2f}, PR={ratings[target_team].mu*2:.1f}")
    for started, match in worlds:
        rt, bt, rs, bs = _parse_match(match)
        if target_team not in rt + bt: continue
        for t in rt + bt:
            if t not in ratings: ratings[t] = TrueSkillRating()
        if rs == 0 and bs == 0: continue
        r_rats = [ratings[t] for t in rt]
        b_rats = [ratings[t] for t in bt]
        before_mu = ratings[target_team].mu
        if rs > bs: weighted_update_trueskill(r_rats, b_rats, abs(rs-bs), weight=1.8, teammate_protect=True)
        elif bs > rs: weighted_update_trueskill(b_rats, r_rats, abs(rs-bs), weight=1.8, teammate_protect=True)
        after_mu = ratings[target_team].mu
        print(f"Match {match['name']} ({rs}-{bs}): mu {before_mu:.2f} -> {after_mu:.2f} (PR {after_mu*2:.1f})")

if __name__ == "__main__":
    diagnose("15442A")
