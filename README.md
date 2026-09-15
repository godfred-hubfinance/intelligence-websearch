# Intelligence Engine Backend

FastAPI backend for collecting, matching, extracting, deduplicating, and serving market intelligence about monitored family offices and wealth-management organisations.

The service collects information from Google News RSS feeds and corporate websites, matches documents to organisations stored in PostgreSQL, uses OpenAI structured extraction to classify relevant events, and exposes the saved intelligence through a REST API.

## Features

- FastAPI REST API with automatic OpenAPI documentation.
- PostgreSQL persistence through SQLAlchemy.
- Organisation-aware Google News searches.
- Corporate website crawling for press releases, news, insights, and articles.
- Deterministic matching using organisation names, aliases, people, and website domains.
- Duplicate detection using exact URLs and fuzzy title similarity.
- Structured event extraction with OpenAI and Pydantic validation.
- Background pipeline triggers through FastAPI `BackgroundTasks`.
- Daily APScheduler job at 06:00 UTC.
- CSV and Excel event exports.
- Excel import utility for monitored organisations.

## Architecture

The main processing flow is:

```text
Collector
  -> StandardDocument
  -> EntityMatcher
  -> Deduplicator
  -> EventExtractor
  -> PostgreSQL persistence
  -> FastAPI API / frontend
```

### Collection

The backend currently supports several collector implementations:

- `GoogleNewsCollector`: queries Google News RSS and resolves Google tracking URLs.
- `WebsiteCollector`: discovers likely news links on organisation websites and extracts article content.
- `RSSCollector`: collects documents from configured RSS feeds.
- `GDELTCollector`: collects documents from GDELT queries.

### Matching

Documents are matched against organisations loaded from PostgreSQL. A match can be produced from:

- The organisation's primary name.
- An alternative name or alias.
- A known person associated with the organisation.
- The organisation's website domain.

Documents that do not meet the matcher threshold are discarded before an OpenAI request is made.

### Deduplication

A document is skipped when either:

1. Its URL already exists in the `documents` table.
2. Its title is sufficiently similar to an existing document title. The current fuzzy title threshold is 80.

### Extraction and persistence

Matched, non-duplicate documents are sent to the OpenAI extractor. The extractor returns a validated event containing the event type, summary, date, people, location, sector, amount, and confidence score. The backend stores the document, event, and relationships to organisations and people in PostgreSQL.

## Requirements

- Python 3.11 or newer.
- PostgreSQL with the application schema loaded.
- An OpenAI API key for event extraction.
- Network access to Google News, monitored websites, and the OpenAI API.
- Optional: Docker and Docker Compose.

The project currently uses PostgreSQL on port `3003` by default. The default local connection string is:

```text
postgresql://postgres:postgres@localhost:3003/intelligence_db
```

Set `DATABASE_URL` when your PostgreSQL host, port, credentials, or database name differs.

## Installation

From the backend directory:

### Windows PowerShell

```powershell
cd backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks script activation, run the commands from `venv\Scripts\python.exe` directly or use Command Prompt:

```bat
venv\Scripts\activate.bat
```

### macOS/Linux

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the backend directory. Do not commit secrets.

```dotenv
DATABASE_URL=postgresql://postgres:postgres@localhost:3003/intelligence_db
OPENAI_API_KEY=your_openai_api_key
FRONTEND_URL=http://localhost:3000
```

### Environment variables

| Variable         | Required           | Description                                                                                                                                                   |
| ---------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`   | No                 | SQLAlchemy PostgreSQL connection string. If omitted, the backend uses `postgresql://postgres:postgres@localhost:3003/intelligence_db`.                        |
| `OPENAI_API_KEY` | Yes for extraction | API key used by `EventExtractor` with the `gpt-4o-mini` model. Collection and matching can run without successful extraction, but events will not be created. |
| `FRONTEND_URL`   | No                 | Additional frontend origin allowed by CORS. `http://localhost:3000` and `http://127.0.0.1:3000` are already allowed.                                          |

## Database setup

The backend expects these logical tables and relationships:

- `organisations`: monitored companies, websites, aliases, locations, and metadata.
- `people`: people associated with monitored organisations.
- `documents`: collected source documents. URLs are unique.
- `events`: extracted intelligence events.
- `event_documents`: event-to-document relationship table.
- `event_people`: event-to-person relationship table.

A database dump is included at `dump.sql`. Load it into an existing PostgreSQL database, for example:

```bash
psql "postgresql://postgres:postgres@localhost:3003/intelligence_db" -f dump.sql
```

The exact `psql` command depends on your PostgreSQL installation and credentials. Verify the connection before starting the API:

```bash
python tests/test_db.py
```

That script prints the organisations and events visible to the configured database connection.

## Import monitored organisations

The Excel importer reads `organisations.xlsx` and skips organisations whose names already exist. It accepts common English and French column names.

Recognised columns include:

| Data              | Accepted column names              |
| ----------------- | ---------------------------------- |
| Organisation name | `societe`, `nom`, `company`        |
| Website           | `site internet`, `site`, `website` |
| LinkedIn URL      | `linkedin`, `linkedin url`         |
| City              | `ville`, `city`                    |
| Country           | `pays`, `country`                  |

Run it from the backend directory:

```bash
python scripts/import_organisations.py
```

The importer normalises website URLs, creates a simple alias when possible, and reports inserted and skipped rows.

## Running the API

Start the development server from the backend directory:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The API is then available at:

- Base URL: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

On application startup, the FastAPI lifespan handler starts APScheduler. On shutdown, it stops the scheduler.

## Running the ingestion pipeline manually

### Organisation-specific Google News scan

`run_pipeline.py` loads every organisation name from the database, processes them in batches of 15, and performs a quoted Google News query for each organisation.

```bash
python run_pipeline.py
```

This is the closest command to the frontend's **Run Live Scan** button. The frontend calls `POST /pipeline/trigger`, which performs the same organisation-aware query construction in a background task.

The current CLI limit is 3 Google News articles per organisation query. The frontend request can supply its own `limit_per_source` value.

### Website-only scan

To crawl the monitored organisations' official websites:

```bash
python scripts/run_website_pipeline.py
```

The script requests up to two articles per website and persists newly extracted events.

### Legacy example entry point

`main.py` is a small example that runs RSS and GDELT queries. It is separate from `run_pipeline.py` and is not the entry point used by the frontend.

```bash
python main.py
```

## Scheduled and manual scan modes

There are two different API scan routes. They are intentionally documented separately because they do not run the same search strategy.

### `POST /pipeline/trigger`

Runs an organisation-aware Google News scan in the background.

Request body:

```json
{
  "organisation_ids": [1, 2],
  "limit_per_source": 5
}
```

Both fields are optional:

- Omit `organisation_ids` to scan all monitored organisations.
- `limit_per_source` defaults to `3` in the request schema.

Example:

```bash
curl -X POST http://localhost:8000/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d "{\"limit_per_source\":5}"
```

The response confirms that the job was queued; it does not wait for extraction to finish:

```json
{
  "status": "queued",
  "message": "Intelligence pipeline triggered in the background.",
  "target_organisations_count": "all"
}
```

### `POST /scheduler/run-now`

Runs the scheduled scan immediately in the background. This path:

1. Searches Google News using broad phrases such as `multi-family office` and `gestion de patrimoine`.
2. Crawls monitored corporate websites.

It does not build one quoted Google News query per organisation. The route is useful for manually invoking the scheduler's full broad scan, while `/pipeline/trigger` is the better route for organisation-specific live scans.

```bash
curl -X POST http://localhost:8000/scheduler/run-now
```

### Daily scheduler

The APScheduler job is registered at application startup and runs daily at **06:00 UTC**. It performs the same broad Google News plus website crawl behavior as `/scheduler/run-now`.

Check scheduler state:

```bash
curl http://localhost:8000/scheduler/status
```

## API reference

### Health

#### `GET /health`

Returns a service health response.

```json
{
  "status": "ok",
  "service": "intelligence-engine"
}
```

### Organisations

#### `GET /organisations`

Returns monitored organisations and their event counts.

Optional query parameter:

- `country`: case-insensitive country filter.

```bash
curl "http://localhost:8000/organisations?country=France"
```

### Events

#### `GET /events`

Returns paginated event records with linked people and source documents.

Supported query parameters:

| Parameter           | Description                                                      |
| ------------------- | ---------------------------------------------------------------- |
| `organisation_id`   | Filter by organisation ID.                                       |
| `organisation_name` | Case-insensitive organisation name search.                       |
| `event_type`        | Case-insensitive event type search.                              |
| `min_confidence`    | Minimum confidence from `0.0` to `1.0`.                          |
| `start_date`        | Include events on or after `YYYY-MM-DD`.                         |
| `end_date`          | Include events on or before `YYYY-MM-DD`.                        |
| `page`              | 1-based page number. Defaults to `1`.                            |
| `page_size`         | Number of records per page, from `1` to `100`. Defaults to `10`. |

Example:

```bash
curl "http://localhost:8000/events?page=1&page_size=10&min_confidence=0.7"
```

The response has this shape:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

#### `GET /events/{event_id}`

Returns one event with its documents and people.

```bash
curl http://localhost:8000/events/42
```

#### `GET /events/export`

Exports events as CSV or Excel.

Supported parameters include `format=csv|xlsx`, `organisation_id`, `organisation_name`, `event_type`, and `min_confidence`.

```bash
curl -L "http://localhost:8000/events/export?format=csv" -o events.csv
curl -L "http://localhost:8000/events/export?format=xlsx" -o events.xlsx
```

## Event taxonomy

The OpenAI extractor is instructed to return one of these event types:

- Investment
- Acquisition
- Divestment
- Appointment
- Departure
- Recruitment
- Partnership
- New office
- Fundraising
- Product/service launch
- Portfolio announcement
- Conference/event
- Strategic announcement
- Other

The frontend currently filters and displays a subset of these values, but the API and database can store the complete taxonomy.

## Testing

The test files are script-style checks and can be run individually from the backend directory:

```bash
python tests/test_matcher.py
python tests/test_deduplicator.py
python tests/test_rss.py
python tests/test_gdelt.py
python tests/test_db.py
```

`tests/test_extractor.py` makes a real OpenAI extraction request and therefore requires a working `OPENAI_API_KEY`, network access, and available API quota:

```bash
python tests/test_extractor.py
```

If you prefer pytest collection, install pytest separately because it is not currently pinned in `requirements.txt`:

```bash
python -m pip install pytest
python -m pytest tests
```

The database and collector checks may access external services or the configured PostgreSQL database. Use test credentials and a test database when appropriate.

## Docker

The backend image can be built directly:

```bash
docker build -t intelligence-backend ./backend
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql://postgres:postgres@host.docker.internal:3003/intelligence_db" \
  -e OPENAI_API_KEY="your_openai_api_key" \
  intelligence-backend
```

The image starts:

```text
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The checked-in `backend/docker-compose.yml` also describes a frontend service and expects a PostgreSQL instance on the host at port `3003`; it does not define a PostgreSQL container. Review its relative build paths before using it from this repository layout, or run the backend image separately as shown above.

## Troubleshooting

### The API cannot connect to PostgreSQL

- Confirm PostgreSQL is running.
- Confirm the database exists and is listening on port `3003`.
- Check `DATABASE_URL` in `.env`.
- Run `python tests/test_db.py` from the backend directory.

### A scan completes but creates no events

This can be expected when:

- Google News returned no articles for the organisation.
- The matcher did not find an organisation, alias, person, or website domain in the document.
- The document was already stored or had a near-duplicate title.
- The OpenAI extractor returned no structured event.
- The document was filtered as an obituary or other excluded personal notice.

Inspect the backend logs for match, deduplication, extraction, and persistence messages.

### The frontend reports that a scan completed but no new item appears

Both scan trigger routes return before background processing is complete. The frontend currently waits approximately 20 seconds before reloading events, but large organisation lists or slow AI requests can take longer. Check the backend logs and refresh the events endpoint after the background task finishes.

### OpenAI extraction fails

- Confirm `OPENAI_API_KEY` is present in the backend process environment.
- Confirm the key has access to the configured model.
- Check network access and API quota.
- Collection and matching logs may still appear even when extraction fails, because extraction happens after collection and matching.

### A website produces no articles

The website collector only follows internal links that look like news or content pages. It falls back to the homepage when no matching links are found, and it requires extractable page content. Sites that rely heavily on JavaScript, block automated requests, or expose no discoverable article links may produce no documents.

## Project layout

```text
backend/
├── api/
│   ├── main.py                 FastAPI application and route handlers
│   └── schemas.py              Pydantic API request/response models
├── collectors/
│   ├── base.py                 Collector base types
│   ├── schemas.py              StandardDocument model
│   ├── google_news_collector.py Google News RSS collector
│   ├── gdelt_collector.py      GDELT collector
│   ├── rss_collector.py        Generic RSS collector
│   └── website_collector.py    Corporate website collector
├── database/
│   ├── connection.py           SQLAlchemy engine and session dependency
│   └── models.py               Organisation, person, document, and event models
├── pipeline/
│   ├── orchestrator.py         End-to-end collection and persistence flow
│   ├── matcher.py              Organisation relevance matching
│   ├── deduplicator.py         URL/title duplicate detection
│   └── extractor.py            OpenAI structured event extraction
├── scheduler/
│   ├── scheduler.py             APScheduler configuration
│   └── tasks.py                 Scheduled scan implementation
├── scripts/
│   ├── import_organisations.py  Excel-to-database importer
│   └── run_website_pipeline.py  Website-only pipeline runner
├── tests/                      Script-style checks
├── dump.sql                    Database dump/schema data
├── run_pipeline.py             Organisation-aware Google News runner
├── main.py                     RSS/GDELT example entry point
├── Dockerfile                  Backend container image
├── docker-compose.yml           Combined deployment configuration
└── requirements.txt             Python dependencies
```

## Operational notes

- Pipeline jobs run in the background when triggered through the API. A successful HTTP response means the job was queued, not that events were already saved.
- The scheduler uses `max_instances=1` to avoid overlapping scheduled runs.
- The pipeline commits each extracted event and updates its in-memory duplicate cache after each successful insert.
- Google News collection defaults to French (`language="fr"`, `country="FR"`).
- Website crawling disables certificate verification for compatibility with sites that have certificate quirks. Use caution when changing this behavior for production deployments.
- Do not expose the API publicly without adding authentication, rate limiting, and production-grade secret management.
