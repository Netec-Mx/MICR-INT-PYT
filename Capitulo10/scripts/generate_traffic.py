import random, time
import httpx

for number in range(30):
    roll = random.random()
    path = "/fail" if roll < 0.1 else f"/products/{'missing' if roll < 0.3 else 'p-1'}"
    try: httpx.get(f"http://localhost:8000{path}", headers={"x-request-id": f"traffic-{number}"}, timeout=2)
    except httpx.HTTPError as error: print(error)
    time.sleep(0.1)
