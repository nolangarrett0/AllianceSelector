import requests
import time
import sys

# RobotEvents API Key
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Cache to avoid hitting the API multiple times for the same event
EVENT_CACHE = {}

def safe_request(url):
    """Make a rate-limited request to the API."""
    time.sleep(0.2)  # Respect rate limits
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 429:
                wait_time = (attempt + 1) * 3
                print(f"\nRate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            if r.status_code >= 500:
                time.sleep(2)
                continue
            # If the response is not valid JSON (e.g. 404 HTML), this will throw an error
            return r.json()
        except Exception as e:
            if attempt == 2:
                # Silently fail on the last attempt so we can fallback gracefully
                pass
            time.sleep(1)
    return None

def get_event_details(event_id):
    """Fetch event details and cache them."""
    if event_id in EVENT_CACHE:
        return EVENT_CACHE[event_id]
    
    data = safe_request(f"https://www.robotevents.com/api/v2/events/{event_id}")
    if data and isinstance(data, dict):
        event = data
        EVENT_CACHE[event_id] = event
        return event
    return None

def is_world_qualifying(event):
    """Determine if an event is a world-qualifying event."""
    if not event:
        return False
    
    level = str(event.get('level', '')).lower()
    name = str(event.get('name', '')).lower()
    
    # Check by level
    if level in ['signature', 'state', 'regional', 'national', 'championship']:
        return True
        
    # Check by name keywords
    keywords = ['signature event', 'state championship', 'regional championship', 'national championship']
    for kw in keywords:
        if kw in name:
            return True
            
    return False

def find_world_championship():
    """Find the High School World Championship for the current season."""
    print("Finding current season...")
    data = safe_request("https://www.robotevents.com/api/v2/seasons?program[]=1")
    if not data or 'data' not in data:
        print("Failed to fetch seasons.")
        return None, None
        
    season_id = None
    for s in data['data']:
        if "Push Back" in s['name'] or "2025" in s['name'] or "2026" in s['name']:
            season_id = s['id']
            print(f"Found Season: {s['name']} (ID: {season_id})")
            break
            
    if not season_id:
        return None, None

    print("\nSearching for High School World Championship event...")
    url = f"https://www.robotevents.com/api/v2/events?season[]={season_id}&per_page=100"
    while url:
        data = safe_request(url)
        if not data or 'data' not in data:
            break
            
        for e in data['data']:
            name = e.get('name', '').lower()
            if 'world championship' in name and 'high school' in name:
                return season_id, e
                
        url = data.get('meta', {}).get('next_page_url')

    return season_id, None

def main():
    print("=" * 60)
    print(" VEX V5 DESIGN AWARD ELIGIBILITY CHECKER ")
    print("=" * 60)
    
    # 1. Fetch the hardcoded event
    sku = "RE-V5RC-26-4025"
    print(f"\nFetching event details for SKU: {sku}...")
    data = safe_request(f"https://www.robotevents.com/api/v2/events?sku={sku}")
    if not data or not data.get('data'):
        print("Event not found with that SKU.")
        sys.exit(1)
    wc_event = data['data'][0]
        
    print(f"\nTarget Event: {wc_event['name']} (SKU: {wc_event['sku']})")
    
    # Extract the correct season_id directly from the event
    if 'season' in wc_event and 'id' in wc_event['season']:
        season_id = wc_event['season']['id']
        print(f"Using Season ID: {season_id} ({wc_event['season'].get('name', 'Unknown')})")
    else:
        print("Warning: Could not determine season ID from the event. Awards might not be found.")
    
    # 2. Find the Spirit division
    divisions = wc_event.get('divisions', [])
    spirit_div = None
    for d in divisions:
        if 'spirit' in str(d.get('name', '')).lower():
            spirit_div = d
            break
            
    if not spirit_div:
        print("\nCould not find a 'Spirit' division in this event.")
        print("Available divisions:")
        for d in divisions:
            print(f"  - {d.get('name')}")
        
        div_name = input("\nEnter the exact name of the division you want to check: ").strip()
        for d in divisions:
            if d.get('name', '').lower() == div_name.lower():
                spirit_div = d
                break
                
        if not spirit_div:
            print("Division not found. Exiting.")
            sys.exit(1)
            
    print(f"\nTarget Division: {spirit_div['name']} (ID: {spirit_div['id']})")
    
    # 3. Get teams in the division
    print("\nFetching teams in division...")
    teams = []
    url = f"https://www.robotevents.com/api/v2/events/{wc_event['id']}/divisions/{spirit_div['id']}/teams?per_page=250"
    data = safe_request(url)
    if data and 'data' in data:
        teams = data['data']
        
    if not teams:
        print("API endpoint for division teams failed or is empty.")
        print("Falling back to reading all teams in the event and matching against the Spirit PDF roster...")
        
        # Hardcoded list of teams from the Spirit Division
        spirit_team_numbers = [
            '39H', '85B', '197E', '295Y', '355A', '550X', '750S', '917X', '1022Z', '1168A', '1430X', '1585Y', '1727R', '1795X', '2011G', '2131F', '2150A', '2393S', '2501T', '2616V', '2930B', '3142C', '3217A', '3632A', '3796F', '4154R',
            '4610C', '4886Y', '5225A', '5691X', '6008X', '6219B', '6603A', '7110H', '7316X', '7618A', '7870X', '8110A', '8568A', '8917B', '9080S', '9257C', '9909C', '10222R', '11101X', '11777J', '13135F', '13722V', '15442A', '16329E', '17711C', '18961B', '20164T',
            '21111A', '22603B', '27258C', '29204E', '32174A', '34020A', '37358A', '39960A', '43146B', '44252S', '47510S', '51581B', '54677A', '56721K', '60053B', '62629X', '64178B', '66994B', '69955X', '71909Z', '74403X', '76624S', '78792E', '80852A', '81988E', '84841Z', '87867D', '91231C', '95071Y',
            '96950Z', '98225F', '98601X', '99751V'
        ]
        
        seen_teams = set()
        all_teams_url = f"https://www.robotevents.com/api/v2/events/{wc_event['id']}/teams?per_page=250"
        while all_teams_url:
            sys.stdout.write(".")
            sys.stdout.flush()
            all_teams_data = safe_request(all_teams_url)
            if not all_teams_data or 'data' not in all_teams_data:
                break
                
            for t in all_teams_data['data']:
                num = t.get('number')
                if num in spirit_team_numbers and num not in seen_teams:
                    seen_teams.add(num)
                    teams.append(t)
                    
            all_teams_url = all_teams_data.get('meta', {}).get('next_page_url')
        print("\n")

    if not teams:
        print("No teams found in this division. (Teams might not be assigned yet, or fallback failed).")
        sys.exit(1)
        
    print(f"Found {len(teams)} teams.")
    
    # 4. Check each team for Design Awards at qualifying events
    print("\nChecking for qualifying Design Awards...\n")
    print(f"{'TEAM':<10} | {'STATUS':<20} | {'DETAILS'}")
    print("-" * 80)
    
    eligible_teams = []
    
    for i, team in enumerate(teams):
        team_number = team.get('number', 'Unknown')
        team_id = team.get('id')
        
        # Give progress update to user without breaking formatting
        sys.stdout.write(f"\rProcessing {i+1}/{len(teams)} (Team {team_number})...       ")
        sys.stdout.flush()
        
        # Fetch awards for this season
        awards_url = f"https://www.robotevents.com/api/v2/teams/{team_id}/awards?season[]={season_id}"
        awards_data = safe_request(awards_url)
        
        found_qualifying_design = False
        qualifying_events = []
        
        if awards_data and 'data' in awards_data:
            for award in awards_data['data']:
                award_title = str(award.get('title', '')).lower()
                
                # Check if it's a Design Award
                if 'design' in award_title:
                    award_event_id = award.get('event', {}).get('id')
                    if award_event_id:
                        event_details = get_event_details(award_event_id)
                        
                        if is_world_qualifying(event_details):
                            found_qualifying_design = True
                            qualifying_events.append(event_details.get('name', 'Unknown Event'))
        
        if found_qualifying_design:
            # Erase progress line and print result
            sys.stdout.write("\r\033[K") 
            print(f"{team_number:<10} | \033[92mELIGIBLE\033[0m             | Won at: {', '.join(qualifying_events)}")
            eligible_teams.append(team_number)
            
    # Clear the progress line at the end
    sys.stdout.write("\r\033[K")
    
    print("-" * 80)
    print(f"\nSummary: Found {len(eligible_teams)} teams in the {spirit_div['name']} division eligible for the Design Award.")
    if eligible_teams:
        print("Eligible teams:", ", ".join(eligible_teams))

if __name__ == "__main__":
    main()
