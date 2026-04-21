import json, os, sys
sys.path.append('..')
from vex_scout_v11 import API_KEY, safe_request, TrueSkillRating, update_trueskill

CACHE = 'cache/season_history.json'
if os.path.exists(CACHE):
    with open(CACHE) as f:
        history = json.load(f)
    
    for team in list(history.keys())[:5]:
        print(team + ": " + str(len(history[team])) + " matches cached")
    print("Total teams cached: " + str(len(history)))
    
    ratings = {}
    all_matches = []
    seen = set()
    for team, t_matches in history.items():
        for m in t_matches:
            eid = m["event_id"]
            mname = m["name"]
            key = str(eid) + "_" + mname
            if key not in seen:
                seen.add(key)
                started = m.get("started") or "2000-01-01"
                all_matches.append((started, m))
    
    all_matches.sort(key=lambda x: x[0])
    print("\nTotal unique matches: " + str(len(all_matches)))
    
    scored = 0
    unscored = 0
    for started, match in all_matches:
        alliances = match.get("alliances", [])
        if isinstance(alliances, list):
            alliance_dict = {}
            for a in alliances:
                alliance_dict[a.get("color")] = a
        else:
            alliance_dict = alliances
        
        red = alliance_dict.get("red", {})
        blue = alliance_dict.get("blue", {})
        red_teams = [t["team"]["name"] for t in red.get("teams", [])]
        blue_teams = [t["team"]["name"] for t in blue.get("teams", [])]
        red_score = red.get("score", 0)
        blue_score = blue.get("score", 0)
        
        for t in red_teams + blue_teams:
            if t not in ratings:
                ratings[t] = TrueSkillRating()
        
        if red_score == 0 and blue_score == 0:
            unscored += 1
            continue
        scored += 1
        
        r_ratings = [ratings[t] for t in red_teams]
        b_ratings = [ratings[t] for t in blue_teams]
        if not r_ratings or not b_ratings:
            continue
        
        margin = abs(red_score - blue_score)
        if red_score > blue_score:
            update_trueskill(r_ratings, b_ratings, margin)
        elif blue_score > red_score:
            update_trueskill(b_ratings, r_ratings, margin)
    
    print("Scored matches: " + str(scored) + ", Unscored: " + str(unscored))
    
    mus = [ratings[t].mu for t in ratings]
    print("\nMin mu: %.2f, Max mu: %.2f, Avg mu: %.2f" % (min(mus), max(mus), sum(mus)/len(mus)))
    print("Total teams with ratings: " + str(len(ratings)))
    
    config_teams = ["8568A","44252S","295Y","20164T","3632A","3796F","1430X","5225A",
                     "21111A","7110H","750S","34020A","71909Z","1585Y","51581B","11101X",
                     "78792E","3217A","98601X","16329E","13135F","60053B","10222R","32174A",
                     "39960A","4154R","17711C","6008X","95071Y","7618A","2393S","18961B",
                     "7870X","355A","98225F","11777J","3142C","56721K","27258C"]
    print("\nSchedule team ratings:")
    for t in config_teams:
        if t in ratings:
            mu = ratings[t].mu
            pr = max(0, min(100, round((mu - 10) * 3.33, 1)))
            print("  %s: mu=%.2f, power_rating=%.1f" % (t, mu, pr))
        else:
            print("  %s: NOT FOUND" % t)
else:
    print("No cache file found")
