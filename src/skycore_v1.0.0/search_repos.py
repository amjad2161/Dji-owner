import urllib.request
import json

repos = [
    ("webodm", "webodm+photogrammetry"),
    ("FAST-Planner", "FAST-Planner+trajectory+UAV"),
    ("aerostack2", "aerostack2+multi-uav"),
    ("mavsdk-drone-show", "mavsdk+drone+show"),
    ("swarm-slam", "swarm-slam+UAV")
]

for name, query in repos:
    try:
        url = f'https://api.github.com/search/repositories?q={query}&sort=stars&per_page=3'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"\n=== {name} ===")
        for item in data.get('items', [])[:3]:
            print(f"{item['full_name']} ({item['stargazers_count']} stars)")
            print(f"  {item['html_url']}")
            print(f"  {item.get('description', '')[:80]}")
    except Exception as e:
        print(f"Error for {name}: {e}")