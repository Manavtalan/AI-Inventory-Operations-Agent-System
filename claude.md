# AI Inventory & Operations Intelligence System
**Module Labs AI — System 2**

## Project Overview

Building a production-grade AI system that eliminates manual inventory tracking for D2C brands. 

**Core Problem:** Every D2C brand manually updates spreadsheets nightly to track inventory, sales, and reorder needs. This takes 2-3 hours per day and is error-prone.

**Solution:** Automated daily inventory reconciliation, reorder intelligence, dead stock detection, and morning WhatsApp reports.

**First Client:** Bluorng Clothing (streetwear brand, ₹20Cr revenue)

---

## Tech Stack

### Backend
- Python 3.11+
- FastAPI (async API framework)
- SQLAlchemy + Alembic (ORM + migrations)
- Celery + Redis (task queue + broker)
- Pydantic v2 (data validation)

### Data
- PostgreSQL 15 (primary database)
- Redis 7 (cache + Celery broker)

### Integrations
- Shopify Admin REST API + Webhooks
- WhatsApp Business API (360dialog/Wati)
- Google Sheets API (gspread)
- Slack Webhooks
- SendGrid (email)

### Infrastructure
- Docker + Docker Compose
- GitHub Actions (CI/CD)
- Sentry (error tracking)
- Railway/DigitalOcean (hosting)

---

## Architecture Principles

1. **Shopify is source of truth** — we sync from Shopify, never maintain parallel inventory
2. **Webhook → Queue → Process** — webhooks acknowledge immediately, processing happens async
3. **Idempotent everything** — every task can run twice with same result
4. **Fail loudly** — no silent failures, log everything with context
5. **Config-driven** — thresholds in YAML, not hardcoded
6. **Production from Day 1** — proper tests, logging, error handling from the start

---

## Project Structure
```
inventory-ops-ai/
├── app/
│   ├── api/              # FastAPI routes and webhook receivers
│   ├── core/             # Config, database, logging, exceptions
│   ├── integrations/     # Shopify, WhatsApp, Google Sheets, Slack
│   ├── services/         # Business logic (reconciliation, velocity, alerts)
│   ├── workers/          # Celery task definitions
│   ├── models/           # SQLAlchemy database models
│   └── schemas/          # Pydantic request/response schemas
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/              # Onboarding, backfill, utilities
├── config/               # YAML brand configurations
├── alembic/              # Database migrations
├── docker/
└── .github/workflows/    # CI/CD
```

---

## Development Phases

### Phase 0 — Foundation (3-4 days) ← WE ARE HERE
- Repository structure
- Docker environment (app, worker, beat, postgres, redis)
- FastAPI skeleton with structured logging
- Settings & secrets management
- Database setup with base models
- Celery configuration
- CI/CD pipeline

### Phase 1 — Shopify Integration (4-5 days)
- Webhook receiver with HMAC validation
- Event storage & audit log
- Event normalization layer
- Shopify REST API client with rate limiting
- Historical backfill script
- Integration tests

### Phase 2 — Reconciliation Engine (5-6 days)
- Inventory data models
- Daily reconciliation Celery task
- Sell velocity calculation
- Google Sheets auto-update
- Inventory snapshot API endpoints

### Phase 3 — Alerts & Reorder (4-5 days)
- Alert detection engine
- WhatsApp delivery service
- Slack delivery service
- Reorder recommendation engine
- Drop performance tracker

### Phase 4 — Reports (4-5 days)
- Morning report generator
- Weekly BI report generator
- Report storage & history
- Delivery reliability layer

### Phase 5 — Dashboard (3-4 days)
- Sentry integration
- Internal ops dashboard
- Client-facing portal (React)
- System health metrics

### Phase 6 — Testing & Launch (3-4 days)
- E2E test suite
- Load testing
- Security audit
- Staging UAT
- Production deployment

---

## Coding Standards

### Python
- Type hints on all functions
- Docstrings on all public functions
- Black formatting (line length 100)
- Ruff linting
- No print statements — use structured logging

### Logging
```python
import structlog
logger = structlog.get_logger(__name__)

logger.info(
    "webhook_received",
    topic=topic,
    event_id=event_id,
    shop_domain=shop_domain
)
```

### Error Handling
```python
try:
    result = await some_operation()
except SpecificError as e:
    logger.error("operation_failed", error=str(e), context=context)
    raise
```

### Database
- Always use async SQLAlchemy
- Always wrap writes in transactions
- Never raw SQL strings (injection risk)
- Proper indexes on all foreign keys and query columns

### Celery Tasks
```python
@celery_app.task(bind=True, max_retries=3, acks_late=True)
def task_name(self, arg):
    try:
        # Do work
        pass
    except Exception as e:
        logger.error("task_failed", error=str(e))
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

### Tests
- Minimum 80% coverage per module
- Use pytest with pytest-asyncio
- Mock all external API calls
- Use fixtures for database setup

---

## Environment Variables Template
```bash
# Application
APP_ENV=development
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=inventory_ops
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Shopify
SHOPIFY_API_KEY=
SHOPIFY_API_SECRET=
SHOPIFY_STORE_DOMAIN=bluorng.myshopify.com
SHOPIFY_WEBHOOK_SECRET=

# WhatsApp
WHATSAPP_API_URL=
WHATSAPP_API_KEY=
WHATSAPP_PHONE_NUMBER=

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=./credentials/google-service-account.json

# Slack
SLACK_WEBHOOK_URL=

# SendGrid
SENDGRID_API_KEY=

# OpenAI
OPENAI_API_KEY=
```

---

## Current Task

**Phase 0, Step 0.4 — Settings & Secrets Management**

Replace raw `os.getenv()` calls with a Pydantic `BaseSettings` class:
- Create `app/core/settings.py` with typed, validated settings
- Update `app/main.py` to use settings object
- Update `.env.example` with all variables documented
- Startup validation should use Settings (missing required var = refused startup with clear error)

---

## Notes for Claude Code

- We're building for production from Day 1 — no shortcuts
- Every step must be completed properly before moving to the next
- Tests are mandatory, not optional
- If you're unsure about something, ask before implementing
- Code quality > speed
- This will be used by a real brand with real money on the line

---

## References

- Full development plan: `/docs/Inventory_Development_Plan.md` (to be created)
- Project overview: `/docs/Inventory_System_Overview.docx` (to be created)