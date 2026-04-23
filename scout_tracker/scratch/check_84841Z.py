import json
import os

filepath = os.path.join("..", "match_predictor", "cache", "season_history.json")
with open(filepath, 'r') as f:
    data = json.load(f)

print(f"Total teams in history: {len(data)}")
print(f"Is 84841Z in history keys? {'84841Z' in data}")
if '84841Z' in data:
    print(f"Matches for 84841Z: {len(data['84841Z'])}")
