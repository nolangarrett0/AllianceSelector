import json
import os

filepath = os.path.join("..", "match_predictor", "cache", "season_history.json")
with open(filepath, 'r') as f:
    history = json.load(f)

team_number = "84841Z"
found_matches = {}

for team, matches in history.items():
    for m in matches:
        match_key = f"{m.get('event_id')}_{m['name']}"
        if match_key in found_matches: continue
        
        involved = False
        for a in m['alliances']:
            teams = [t['team']['name'] for t in a['teams']]
            if team_number in teams:
                involved = True
        
        if involved:
            found_matches[match_key] = m

print(f"Found {len(found_matches)} matches for {team_number} in history.")
for k, m in sorted(found_matches.items()):
    alliances = m['alliances']
    red = [t['team']['name'] for t in alliances[0]['teams']]
    blue = [t['team']['name'] for t in alliances[1]['teams']]
    rs = alliances[0]['score']
    bs = alliances[1]['score']
    print(f"  {k}: {red} ({rs}) vs {blue} ({bs})")
