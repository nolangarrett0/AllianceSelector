import requests

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"
headers = {"Authorization": f"Bearer {API_KEY}"}

def main():
    print("Finding 2026 season...")
    url = "https://www.robotevents.com/api/v2/seasons?program[]=1"
    r = requests.get(url, headers=headers)
    seasons = r.json().get('data', [])
    current_season_id = None
    for s in seasons:
        if "Push Back" in s['name'] or "2025" in s['name'] or "2026" in s['name']:
            current_season_id = s['id']
            break
            
    if not current_season_id:
        print("Season not found!")
        return
        
    print(f"Season ID: {current_season_id}")
    
    # Let's search events by level = "World" or name = "World"
    # Actually, RobotEvents has event_level. 'World' is an event level.
    print("Searching for World Championship event...")
    # There are query parameters for level
    url = f"https://www.robotevents.com/api/v2/events?season[]={current_season_id}&level[]=World"
    r = requests.get(url, headers=headers)
    events = r.json().get('data', [])
    for e in events:
        print(f"Found World Event: {e['name']} ({e['sku']})")
        # Check if it has divisions
        if 'divisions' in e:
            for div in e['divisions']:
                print(f"  Division: {div['name']} (ID: {div['id']})")
                if "Spirit" in div['name']:
                    print("  *** FOUND SPIRIT DIVISION ***")

if __name__ == "__main__":
    main()
