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

def count_matches(team_number):
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
    
    count = 0
    wins = 0
    for m in matches:
        found = False
        won = False
        for a in m['alliances']:
            teams = [t['team']['name'] for t in a['teams']]
            if team_number in teams:
                found = True
                other_score = 0
                for a2 in m['alliances']:
                    if a2['color'] != a['color']:
                        other_score = a2['score']
                if a['score'] > other_score:
                    won = True
        if found:
            count += 1
            if won: wins += 1
            
    print(f"Team {team_number} has played {count} matches, wins: {wins}")

if __name__ == "__main__":
    count_matches("84841Z")
