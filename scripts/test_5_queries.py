import sys
import json
JARVIS_DIR = r"C:\Users\Akshay aravind .rv\operation_jarvis"
if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)

from registry.internet_gateway import InternetGateway

gw = InternetGateway()

queries = [
    "Who is the current CEO of NVIDIA?",
    "NVIDIA China spy scandal Jensen Huang resignation",
    "Israeli election Prime Minister",
    "first Muslim elected 2026 US midterm elections",
    "SpaceX Starship news"
]

for q in queries:
    print(f"\n==========================================")
    print(f"QUERY: {q}")
    news = gw.search_news(q, max_results=3)
    print(f"News hits: {len(news)}")
    for n in news:
        print(f"  - Title: {n.get('title')}")
        print(f"    Date:  {n.get('published_date')}")
        print(f"    URL:   {n.get('url')}")
    
    if not news:
        u = gw.unified_search(q, max_results=3)
        print(f"Unified hits: {len(u.get('sources', []))}")
        for s in u.get('sources', []):
            print(f"  - Title: {s.get('title')} ({s.get('publisher')})")
            print(f"    Date:  {s.get('published_date')}")
            print(f"    URL:   {s.get('url')}")
