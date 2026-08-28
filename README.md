# 🚀 LinkedIn Profile API

A production-ready, hosted API that accepts a LinkedIn profile URL and returns structured, comprehensive profile data as JSON.

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

```text
                    ┌────────────────────────┐
                    │      Client / UI        │
                    └───────────┬────────────┘
                                │
                                │ POST /api/profile
                                ▼
                    ┌────────────────────────┐
                    │     FastAPI Router      │
                    │   (Pydantic Validate)   │
                    └───────────┬────────────┘
                                │
                  Is LINKEDIN_LI_AT_COOKIE set?
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
           [YES]                         [NO / FALLBACK]
              │                                   │
              ▼                                   ▼
┌───────────────────────────┐       ┌───────────────────────────┐
│   LinkedIn Voyager API    │       │     Captapi API Provider  │
│ (Internal Reverse-Eng API)│       │     (Live Scrape Provider)│
└────────────┬──────────────┘       └─────────────┬─────────────┘
             │                                    │
             │                                    │
             │                                    ▼
             │                     ┌───────────────────────────┐
             │                     │ Smart Parser & Extractor  │
             │                     │ (Skills + Fallback Enrich)│
             │                     └─────────────┬─────────────┘
             │                                   │
             └──────────────────┬────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Structured JSON Output │
                    │   (ProfileResponse)    │
                    └────────────────────────┘
```

### Dual Data-Access Strategy

#### 1. Authenticated Voyager Client

`app/services/linkedin_voyager.py`

When a LinkedIn session cookie (`li_at`) is supplied through environment variables, the backend directly calls LinkedIn's internal Voyager REST API:

```text
/voyager/api/identity/profiles/{slug}/profileView
```

The service attempts to retrieve detailed profile information including education, skills, experience, and languages.

#### 2. Captapi + Fallback Enricher

`app/services/captapi.py`  
`app/services/parser.py`

If no session cookie is configured, or if the session expires, the application can use Captapi with parser-based extraction and fallback enrichment.

---

## 📡 API Reference

### 1. `POST /api/profile`

Fetches and structures profile data for a given LinkedIn URL.

#### Request Body

```json
{
  "linkedin_url": "https://www.linkedin.com/in/example/"
}
```

#### Example Response

```json
{
  "profile_url": "https://www.linkedin.com/in/example/",
  "name": "John Doe",
  "headline": "Software Engineer",
  "location": "Hyderabad, India",
  "about": "Software engineer with experience building scalable applications.",
  "profile_images": {
    "profile": "https://example.com/profile.jpg",
    "background": null
  },
  "experience": [
    {
      "title": "Software Engineer",
      "company": "Example Technologies",
      "location": "Hyderabad, India",
      "start_date": "Jan 2024",
      "end_date": null,
      "description": "Building backend and full-stack applications."
    }
  ],
  "education": [
    {
      "institution": "Example University",
      "degree": "Bachelor of Technology",
      "field_of_study": "Computer Science",
      "start_date": "2020",
      "end_date": "2024",
      "description": null
    }
  ],
  "skills": [
    "Python",
    "FastAPI",
    "React",
    "SQL",
    "REST APIs"
  ],
  "certifications": [],
  "languages": [
    {
      "name": "English",
      "proficiency": "Professional"
    }
  ]
}
```

> The actual fields returned depend on the information available through the configured data-access method. Missing information is returned as `null` or an empty array where appropriate.

### 2. `GET /health`

Liveness endpoint:

```json
{
  "status": "ok"
}
```

### 3. `GET /docs`

Interactive Swagger UI for testing the API.

### 4. `GET /redoc`

Alternative API documentation using ReDoc.

---

## 🛠️ Local Setup & Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/srikanthyadav73/linkedin-profile-api.git
cd linkedin-profile-api
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

#### Windows

```bash
venv\Scripts\activate
```

#### macOS / Linux

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env`.

#### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

#### macOS / Linux

```bash
cp .env.example .env
```

Configure the required environment variables in `.env`.

Example:

```ini
ENVIRONMENT=development
LOG_LEVEL=INFO

# Captapi configuration
CAPTAPI_API_KEY=your_captapi_key_here

# Optional LinkedIn authenticated session configuration
LINKEDIN_LI_AT_COOKIE=your_li_at_cookie_here
```

**Never commit `.env` or any credentials to GitHub.**

### 5. Start the development server

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000/
```

to access the dashboard.

API documentation:

```text
http://localhost:8000/docs
```

---

## 🧪 Running Tests

Run the automated pytest suite:

```bash
pytest
```

The test suite covers areas such as:

- API endpoints
- Profile parsing
- URL validation
- Profile routes
- LinkedIn data-access logic

---

## 🚢 Deployment Guide

### Deploy to Render

1. Push the repository to GitHub.
2. Create a new **Web Service** on Render.
3. Connect the GitHub repository.
4. Configure the required environment variables.
5. Deploy the service.
6. Verify the deployed HTTPS endpoint.
7. Test `/health`, `/docs`, and `/api/profile`.

Example environment variables:

```text
CAPTAPI_API_KEY=your_key
LINKEDIN_LI_AT_COOKIE=your_cookie
```

The project includes:

- `render.yaml`
- `Dockerfile`
- `Procfile`

for deployment configuration.

---

## ⚠️ Known Limitations

### 1. LinkedIn Rate Limits

Repeated requests to LinkedIn-related endpoints may trigger rate limits or additional verification requirements.

### 2. Session Cookie Lifespan

If an authenticated `li_at` session cookie is used, the session may expire and require renewal.

### 3. Private Profiles

Profiles with restricted visibility may not expose all information required by the API.

### 4. Data Availability

Not every LinkedIn profile contains every section. For example, some profiles may not have:

- About
- Education
- Skills
- Certifications
- Languages
- Profile images

When information is unavailable, the API returns `null` or an empty array instead of fabricating data.

### 5. External Data Sources

The availability and completeness of profile information depends on the configured LinkedIn data-access method and any external provider being used.

---

## 🔒 Security & Privacy

- Secrets are loaded through environment variables.
- `.env` is excluded from Git.
- API keys and session credentials must never be committed.
- Sensitive credentials should not be included in application logs.
- Request processing should avoid exposing authentication cookies or tokens in API responses.
- External-service credentials should be stored only in the deployment platform's secure environment-variable configuration.

---

## 📁 Project Structure

```text
linkedin-profile-api/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   │
│   ├── models/
│   │   ├── request.py
│   │   └── response.py
│   │
│   ├── routes/
│   │   └── profile.py
│   │
│   ├── services/
│   │   ├── captapi.py
│   │   ├── enricher.py
│   │   ├── linkedin_voyager.py
│   │   └── parser.py
│   │
│   └── utils/
│       ├── exceptions.py
│       └── validator.py
│
├── static/
│   └── index.html
│
├── tests/
│   ├── test_api.py
│   ├── test_parser.py
│   ├── test_profile_route.py
│   ├── test_validator.py
│   └── test_voyager.py
│
├── .env.example
├── .gitignore
├── Dockerfile
├── Procfile
├── render.yaml
├── requirements.txt
└── README.md
```

---

## 🎯 Project Objective

The objective of this project is to provide a simple API interface for extracting and normalizing available LinkedIn profile information.

Instead of requiring a client to understand the underlying data retrieval process, the client only needs to provide:

```json
{
  "linkedin_url": "https://www.linkedin.com/in/example/"
}
```

The API handles retrieval, parsing, normalization, and structured JSON generation.

---

## 🚀 Future Improvements

Potential future improvements include:

- Improved profile-field coverage
- Better handling of incomplete profiles
- More robust error handling
- Additional profile metadata
- Improved caching
- Request rate limiting
- Background processing for large workloads
- Expanded automated test coverage
- Monitoring and observability
