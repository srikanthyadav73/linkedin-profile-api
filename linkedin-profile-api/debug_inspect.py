import json, pathlib
data = json.loads(pathlib.Path("debug_output/voyager_1_dash_memberIdentity.json").read_text(encoding="utf-8"))
edu_items = [x for x in data.get("included", []) if "Education" in x.get("$type", "")]
print("Education count:", len(edu_items))
for e in edu_items:
    print(json.dumps(e, indent=2, ensure_ascii=False))

print("\n\n--- PROFILE ELEMENT ---")
profile_items = [x for x in data.get("included", []) if "Profile" in x.get("$type", "") and "Member" not in x.get("$type", "")]
for p in profile_items[:2]:
    print(json.dumps(p, indent=2, ensure_ascii=False)[:2000])
