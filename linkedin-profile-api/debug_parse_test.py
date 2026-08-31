"""
Test the _parse_dash_payload function against the cached debug JSON.
Run:  venv\Scripts\python.exe debug_parse_test.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from app.services.linkedin_voyager import _parse_dash_payload

data = json.loads(pathlib.Path("debug_output/voyager_1_dash_memberIdentity.json").read_text(encoding="utf-8"))

result = _parse_dash_payload(data, "https://www.linkedin.com/in/madan-surthani-7a90571ba/", "madan-surthani-7a90571ba")

print("=" * 60)
print(f"Name:       {result.name}")
print(f"Headline:   {result.headline}")
print(f"Location:   {result.location}")
print(f"Experience: {len(result.experience)} items")
print(f"Education:  {len(result.education)} items")
print(f"Skills:     {len(result.skills)} items")
print(f"Certs:      {len(result.certifications)} items")
print(f"Languages:  {len(result.languages)} items")
print()

print("EDUCATION DETAILS:")
for e in result.education:
    print(f"  - {e.institution} | {e.degree} | {e.field_of_study} | {e.start_date} - {e.end_date}")

print()
print("SKILLS (first 10):")
for s in result.skills[:10]:
    print(f"  - {s}")
