import sys
import traceback
JARVIS_DIR = r"C:\Users\Akshay aravind .rv\operation_jarvis"
if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)

from registry.internet_gateway import InternetGateway

gw = InternetGateway()
print("1. Testing query sanitization:")
q = "Who is the current CEO of NVIDIA?"
sanitized = gw.sanitize_outgoing_query(q)
print(f"Original: '{q}' -> Sanitized: '{sanitized}'")

print("\n2. Testing fetch_url directly on google news:")
import urllib.parse
url = f"https://news.google.com/rss/search?q={urllib.parse.quote(sanitized)}&hl=en-IN&gl=IN&ceid=IN:en"
print(f"URL: {url}")
try:
    res = gw.fetch_url(url)
    print(f"fetch_url success: {res.get('ok')}, status_code: {res.get('status_code')}")
    print(f"content length: {len(res.get('content', ''))}")
    print(f"content preview: {res.get('content', '')[:500]}")
except Exception as e:
    print(f"fetch_url error: {e}")
    traceback.print_exc()

print("\n3. Testing search_news directly:")
try:
    hits = gw.search_news(q)
    print(f"search_news hits: {len(hits)}")
    for h in hits:
        print(f"  Hit: {h}")
except Exception as e:
    print(f"search_news error: {e}")
    traceback.print_exc()

print("\n4. Testing unified_search:")
try:
    u_hits = gw.unified_search(q)
    print(f"unified_search sources: {len(u_hits.get('sources', []))}")
    for s in u_hits.get('sources', []):
        print(f"  Source: {s.get('title')} ({s.get('publisher')}) - {s.get('url')}")
except Exception as e:
    print(f"unified_search error: {e}")
    traceback.print_exc()
