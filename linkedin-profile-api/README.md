# 🚀 LinkedIn Profile API

> A production-ready, hosted API that accepts any LinkedIn profile URL and returns structured, comprehensive profile data as JSON.

Built with **FastAPI**, **Pydantic v2**, and **httpx**, featuring a dual-layer data architecture: **Reverse-Engineered LinkedIn Voyager Internal API** with fallback to **Captapi Scraping & Intelligent Keyword Extraction**.

---

## 📋 Features

- 👤 **Full Profile Information**: Name, headline, location, about summary, and profile photo.
- 💼 **Experience History**: Titles, companies, locations, parsed dates, and descriptions.
- 🎓 **Education Details**: Institutions, degrees, fields of study, start & end dates.
- ⚡ **Skills Extraction**: Full skills list parsed directly from LinkedIn or extracted via keyword NER from experiences & projects.
- 🏆 **Certifications**: Certificate names, issuing authorities, credential IDs, and links.
- 🌐 **Languages**: Spoken languages with proficiency levels.
- 💻 **Modern Dashboard UI**: Interactive dashboard at `/` to test profiles live, inspect cards, and copy JSON.
- 📖 **Interactive API Docs**: Auto-generated Swagger UI available at `/docs` and ReDoc at `/redoc`.

---

## 🏗️ Architecture & Approach

```
                    ┌────────────────────────┐
                    │      Client / UI       │
                    └───────────┬────────────┘
                                │ POST /api/profile
                                ▼
                    ┌────────────────────────┐
                    │     FastAPI Router     │
                    │   (Pydantic Validate)  │
                    └───────────┬────────────┘
                                │
                 Is LINKEDIN_LI_AT_COOKIE set?
                                │
            ┌───────────────────┴───────────────────┐
     [YES]  │                                       │  [NO / Fallback]
            ▼                                       ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│ LinkedIn Voyager API      │         │ Captapi API Provider      │
│ (Internal Reverse-Eng API)│         │ (Live Scrape Provider)    │
└───────────┬───────────────┘         └─────────────┬─────────────┘
            │                                       │
            │ (100% Unmasked Data)                  │ (Raw Scrape Data)
            │                                       ▼
            │                         ┌───────────────────────────┐
            │                         │ Smart Parser & Extractor  │
            │                         │ (Skills + Fallback Enrich)│
            │                         └─────────────┬─────────────┘
            │                                       │
            └───────────────────┬───────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Structured JSON Output │
                    │   (ProfileResponse)    │
                    └────────────────────────┘
```

### Dual Data-Access Strategy:
1. **Authenticated Voyager Client (`app/services/linkedin_voyager.py`)**:
   - When a LinkedIn session cookie (`li_at`) is supplied in environment variables, the backend directly calls LinkedIn's internal Voyager REST API (`/voyager/api/identity/profiles/{slug}/profileView`).
   - Returns 100% unmasked, complete data directly from LinkedIn's internal service, including all education, skills, and languages.
2. **Captapi + Fallback Enricher (`app/services/captapi.py` & `app/services/parser.py`)**:
   - If no session cookie is configured or if the session expires, the app seamlessly uses Captapi with smart keyword extraction for skills and fallback enrichers.

---

## 📡 API Reference

### 1. `POST /api/profile`
Fetches and structures profile data for a given LinkedIn URL.

#### Request Body
```json
{
  "linkedin_url": "https://www.linkedin.com/in/williamhgates/"
}
```

#### Example Response (`200 OK`)
```json
{
  "profile_url": "https://www.linkedin.com/in/williamhgates/",
  "name": "Bill Gates",
  "headline": "Co-chair, Bill & Melinda Gates Foundation",
  "location": "Seattle, Washington, United States",
  "about": "Co-chair of the Bill & Melinda Gates Foundation...",
  "profile_images": {
    "profile": "https://media.licdn.com/dms/image/v2/...",
    "background": null
  },
  "experience": [
    {
      "title": "Co-chair",
      "company": "Bill & Melinda Gates Foundation",
      "location": "Seattle, WA",
      "start_date": "Jan 2000",
      "end_date": null,
      "description": "Dedicated to improving global health and education."
    }
  ],
  "education": [
    {
      "institution": "Harvard University",
      "degree": "Honorary Doctorate / Student",
      "field_of_study": "Computer Science & Pre-Law",
      "start_date": "1973",
      "end_date": "1975",
      "description": null
    }
  ],
  "skills": [
    "Software Development",
    "Philanthropy",
    "Public Speaking",
    "Leadership"
  ],
  "certifications": [],
  "languages": [
    {
      "name": "English",
      "proficiency": "Native or bilingual"
    }
  ]
}
```

### 2. `GET /health`
Liveness probe returning `{"status": "ok"}`.

### 3. `GET /docs`
Interactive Swagger UI testing environment.

---

## 🛠️ Local Setup & Quickstart

### 1. Clone the repository
```bash
git clone https://github.com/your-username/linkedin-profile-api.git
cd linkedin-profile-api
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env`:
```ini
ENVIRONMENT=development
LOG_LEVEL=INFO

# Option A: Captapi Key (free at https://captapi.com/dashboard)
CAPTAPI_API_KEY=your_captapi_key_here

# Option B (Recommended for 100% data): LinkedIn Session Cookie (li_at)
# Inspect DevTools -> Application -> Cookies -> linkedin.com -> li_at
LINKEDIN_LI_AT_COOKIE=your_li_at_cookie_here
```

### 5. Start the development server
```bash
uvicorn app.main:app --reload
```
Open **`http://localhost:8000/`** to view the interactive dashboard.

---

## 🧪 Running Tests

Execute the automated pytest suite:
```bash
pytest
```

---

## 🚢 Deployment Guide

### Deploy to Render
1. Push your repository to GitHub.
2. Go to [Render.com](https://render.com) and create a new **Web Service** pointing to your repository.
3. Set Environment variables in the Render dashboard:
   - `CAPTAPI_API_KEY`: Your Captapi key.
   - `LINKEDIN_LI_AT_COOKIE`: *(Optional)* Your `li_at` cookie.
4. Render will automatically build using the included [`render.yaml`](./render.yaml) or [`Dockerfile`](./Dockerfile).

---

## ⚠️ Known Limitations

1. **LinkedIn Rate Limits**: Repeated unauthenticated requests from the same IP to LinkedIn's public endpoint may trigger temporary 429 rate limits or captcha challenges. Using Captapi or an authenticated `li_at` cookie mitigates this.
2. **Session Cookie Lifespan**: If using `LINKEDIN_LI_AT_COOKIE`, LinkedIn session cookies typically expire after several weeks to a year, requiring periodic renewal.
3. **Private Profiles**: Profiles set to strict 100% private visibility on LinkedIn are inaccessible to logged-out users and return HTTP 404.

---

## 🔒 Security & Privacy

- All secrets and API keys are loaded via environment variables using `pydantic-settings`.
- `.gitignore` prevents `.env` or sensitive session files from ever being committed to Git.
- Request/response logs strip authorization tokens and sensitive cookies.
