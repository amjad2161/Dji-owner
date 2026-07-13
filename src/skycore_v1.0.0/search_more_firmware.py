import urllib.request
import json

repos = [
    ("inav_firmware", "inav+firmware+flight"),
    ("iNav_flight", "iNavFlight/inav"),
    ("cleanflight_configurator", "cleanflight+configurator"),
    ("betaflight_configurator", "betaflight+configurator"),
    ("mission_planner", "ardupilot+mission+planner"),
    ("dronekit", "dronkitpython+dronekit"),
    ("pymavlink", "ArduPilot/pymavlink"),
    ("mavproxy", "tridge/MPU+mavproxy")
]

for name, query in repos:
    try:
        url = f'https://api.github.com/search/repositories?q={query}&sort=stars&per_page=3'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"\n=== {name} ===")
        for item in data.get('items', [])[:1]:
            desc = item.get('description', '')
            if desc:
                desc = desc.encode('ascii', 'ignore').decode('ascii')
            print(f"{item['full_name']} ({item['stargazers_count']} stars)")
            print(f"  {item['html_url']}")
            print(f"  {desc[:80]}")
    except Exception as e:
        print(f"Error for {name}: {e}")