import os
import sys
import json
import requests
import time

# Add root directory to path to import from vex_scout_v11
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root)
from vex_scout_v11 import API_KEY

def safe_request(url, headers):
    for i in range(3):
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200: return r.json()
            if r.status_code == 429: time.sleep(1)
        except: time.sleep(1)
    return None

def list_matches(team_number):
    EVENT_ID = 64025
    DIVISION_ID = 7
    HEADERS = {"Authorization": f"Bearer {API_KEY}"}
    
    matches = []
    page = 1
    while True:
        url = f"https://www.robotevents.com/api/v2/events/{EVENT_ID}/divisions/{DIVISION_ID}/matches?per_page=250&page={page}"
        data = safe_request(url, HEADERS)
        if not data or not data.get('data'):
            break
        for m in data['data']:
            matches.append(m)
        if page >= data['meta']['last_page']:
            break
        page += 1
    
    print(f"Matches for {team_number} at Worlds:")
    for m in matches:
        involved = False
        team_color = ""
        for a in m['alliances']:
            teams = [t['team']['name'] for t in a['teams']]
            if team_number in teams:
                involved = True
                team_color = a['color']
        
        if involved:
            alliances = m['alliances']
            red = [t['team']['name'] for t in alliances[0]['teams']]
            blue = [t['team']['name'] for t in alliances[1]['teams']]
            rs = alliances[0]['score']
            bs = alliances[1]['score']
            
            outcome = "UNKNOWN"
            if rs != 0 or bs != 0:
                if (team_color == 'red' and rs > bs) or (team_color == 'blue' and bs > rs):
                    outcome = "WIN"
                elif rs == bs:
                    outcome = "TIE"
                else:
                    outcome = "LOSS"
            
            print(f"  {m['name']} ({outcome}): {red} ({rs}) vs {blue} ({bs})")

if __name__ == "__main__":
    list_matches("84841Z")
