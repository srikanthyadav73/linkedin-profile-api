import asyncio
import logging
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).parent))

logging.basicConfig(level=logging.INFO)

from app.services.linkedin_voyager import fetch_voyager_profile


async def main() -> None:
    url = "https://www.linkedin.com/in/madan-surthani-7a90571ba/"
    print(f"\nFetching via Voyager: {url}\n{'─'*60}")
    try:
        data = await fetch_voyager_profile(url)
        print("\nSUCCESS!")
        print("Name:", data.name)
        print("Education Count:", len(data.education))
        print("Education Items:", data.education)
        print("Skills Count:", len(data.skills))
    except Exception as e:
        print("\nERROR FROM VOYAGER:", type(e), e)
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


