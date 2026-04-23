import json
import os

filepath = os.path.join("..", "match_predictor", "cache", "season_history.json")
with open(filepath, 'r') as f:
    data = json.load(f)

event_ids = set()
for team, matches in data.items():
    for m in matches:
        event_ids.add(m.get('event_id'))

print(f"Number of unique event IDs: {len(event_ids)}")
print(f"Is 64025 in history? {64025 in event_ids}")
if 64025 in event_ids:
    count = 0
    for team, matches in data.items():
        for m in matches:
            if m.get('event_id') == 64025: count += 1
    print(f"Total matches for 64025 in history: {count}")
