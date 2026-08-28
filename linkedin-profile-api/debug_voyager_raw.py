"""
Raw LinkedIn Voyager Debug Script — tests all 3 endpoint strategies.
Run:  venv\Scripts\python.exe debug_voyager_raw.py
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import httpx
from dotenv import load_dotenv
import os

load_dotenv()

LI_AT = os.getenv("LINKEDIN_LI_AT_COOKIE", "").strip()
if not LI_AT:
    print("ERROR: LINKEDIN_LI_AT_COOKIE not set in .env")
    sys.exit(1)

JSESSIONID = "ajax:9876543210123"
USERNAME = "madan-surthani-7a90571ba"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.linkedin.normalized+json+2.1",
    "Accept-Language": "en-US,en;q=0.9",
    "x-restli-protocol-version": "2.0.0",
    "x-li-lang": "en_US",
    "x-li-track": '{"clientVersion":"1.13.9840"}',
    "x-li-page-instance": "urn:li:page:d_flagship3_profile_view_base;1234567890",
    "csrf-token": JSESSIONID,
    "referer": f"https://www.linkedin.com/in/{USERNAME}/",
}
COOKIES = {"li_at": LI_AT, "JSESSIONID": f'"{JSESSIONID}"'}

OUT_DIR = pathlib.Path("debug_output")
OUT_DIR.mkdir(exist_ok=True)


async def test_url(client: httpx.AsyncClient, label: str, url: str) -> None:
    print(f"\n{'='*60}")
    print(f"Testing [{label}]")
    print(f"URL: {url}")
    res = await client.get(url)
    print(f"HTTP Status: {res.status_code}")

    out_file = OUT_DIR / f"voyager_{label.replace(' ', '_')}.json"

    if res.status_code == 200:
        try:
            data = res.json()
            out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            print(f"Saved: {out_file.absolute()}")
            # Look for education
            elements = data.get("elements", [])
            included = data.get("included", [])
            print(f"  elements count: {len(elements)}")
            print(f"  included count: {len(included)}")
            for item in included:
                t = item.get("$type", "")
                if "ducation" in t or "kill" in t or "anguage" in t:
                    print(f"  >> Interesting type: {t}")
            if elements and isinstance(elements[0], dict):
                top_keys = list(elements[0].keys())[:15]
                print(f"  first element keys: {top_keys}")
                for key in ["educationView", "skillView", "positionView"]:
                    if key in elements[0]:
                        count = len((elements[0][key] or {}).get("elements", []))
                        print(f"  >> {key}: {count} items")
        except Exception as e:
            print(f"JSON parse error: {e}")
            print(f"Body: {res.text[:500]}")
    else:
        print(f"Response: {res.text[:300]}")


async def main() -> None:
    print(f"li_at (first 25 chars): {LI_AT[:25]}...")
    print(f"Username: {USERNAME}")

    async with httpx.AsyncClient(
        timeout=20.0, follow_redirects=True, headers=HEADERS, cookies=COOKIES
    ) as client:
        await test_url(client, "1 dash memberIdentity",
            f"https://www.linkedin.com/voyager/api/identity/dash/profiles"
            f"?q=memberIdentity&memberIdentity={USERNAME}"
            f"&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-86"
        )
        await test_url(client, "2 profileView",
            f"https://www.linkedin.com/voyager/api/identity/profiles/{USERNAME}/profileView"
        )
        await test_url(client, "3 basic profile",
            f"https://www.linkedin.com/voyager/api/identity/profiles/{USERNAME}"
        )
        await test_url(client, "4 educations",
            f"https://www.linkedin.com/voyager/api/identity/profiles/{USERNAME}/educations"
        )
        await test_url(client, "5 skills",
            f"https://www.linkedin.com/voyager/api/identity/profiles/{USERNAME}/skills"
        )
        await test_url(client, "6 positions",
            f"https://www.linkedin.com/voyager/api/identity/profiles/{USERNAME}/positions"
        )

    print("\n\nDone! Check debug_output/ folder for saved JSON files.")


if __name__ == "__main__":
    asyncio.run(main())
