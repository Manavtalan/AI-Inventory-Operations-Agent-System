# AI Inventory & Operations Intelligence System
## Production Development Plan — Single Brand
### Module Labs AI — System 2

---

> **Non-Negotiable Standards (Applies to Every Single Step)**
> - Every external API call has retry logic with exponential backoff. No exceptions.
> - Every Celery task is idempotent. Running it twice must produce the same result.
> - Every database write is wrapped in a transaction.
> - Every failure is logged with full context. No silent failures anywhere.
> - Minimum 80% test coverage per module before moving to the next phase.
> - No hardcoded values. Everything configurable via environment variables or YAML.
> - Every new table has proper indexes on all frequently queried columns.
> - We build for one brand first but architect so multi-tenancy can be added without rewriting.

---

## PHASE 0 — Foundation & Environment Setup
**Duration: 3–4 Days**
**Goal: A production-ready project skeleton. Not a single line of business logic until this is solid.**

---

### Step 0.1 — Repository & Project Structure

Create the GitHub repository. Set up branch strategy from Day 1:
- `main` — production only, no direct commits ever
- `staging` — mirrors production, used for UAT
- `dev` — integration branch
- Feature branches off `dev`

Project structure:

```
inventory-ops-ai/
├── app/
│   ├── api/                  # FastAPI routes and webhook receivers
│   ├── core/                 # Config, database, logging, exceptions, middleware
│   ├── integrations/         # Shopify, WhatsApp, Google Sheets, Slack connectors
│   ├── services/             # Business logic — reconciliation, velocity, alerts
│   ├── workers/              # Celery task definitions
│   ├── models/               # SQLAlchemy database models
│   ├── schemas/              # Pydantic request/response schemas
│   └── utils/                # Shared utilities — date helpers, formatters
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/             # Recorded API responses, seed data
├── scripts/                  # Onboarding, backfill, seed scripts
├── config/                   # YAML brand configuration files
├── docker/
├── .github/workflows/        # CI/CD pipelines
├── alembic/                  # Database migrations
├── .env.example
├── docker-compose.yml
├── docker-compose.prod.yml
└── pyproject.toml
```

---

### Step 0.2 — Docker Environment

Write `docker-compose.yml` with these services:

- **app** — FastAPI application container (Python 3.11-slim)
- **worker** — Celery worker container (same image as app)
- **beat** — Celery beat scheduler (scheduled tasks like daily reconciliation)
- **postgres** — PostgreSQL 15 with persistent volume
- **redis** — Redis 7 with persistent volume
- **flower** — Celery monitoring UI (development only, never in prod compose)

Every service must define health checks. App and worker containers must wait for postgres and redis to be healthy before starting. This prevents the "started before DB was ready" failures that are invisible in dev but catastrophic in production.

Write both `docker-compose.yml` (dev, includes flower, verbose logging) and `docker-compose.prod.yml` (production, nginx included, no flower, minimal logging to stdout).

---

### Step 0.3 — Core Application Setup

Set up FastAPI with production configuration from day one.

Use an application factory pattern — a `create_app()` function that assembles the FastAPI instance with all middleware, routers, and startup/shutdown hooks. This makes testing trivial — you create a test app instance without starting servers.

Production requirements:
- Structured JSON logging via `structlog`. Every log line is a JSON object with: timestamp, level, service name, request_id, message, and any additional context. Never use print statements. Never use unstructured logging.
- Request ID middleware — every incoming HTTP request gets a UUID that flows through all downstream log statements, Celery tasks spawned from that request, and database operations. When something goes wrong, you can trace the entire lifecycle of a request from one ID.
- Global exception handler — catches every unhandled exception, logs it with full context including stack trace, and returns a safe JSON error response. The client never sees a Python stack trace.
- Health check endpoint at `GET /health` — returns status of database connectivity, Redis connectivity, and Celery worker availability. This is what your deployment platform pings. If it returns non-200, deployment is considered failed.
- Startup validation — on application startup, verify all required environment variables are present and all required services are reachable. If anything is wrong, refuse to start with a clear error message. A silent startup with broken config is worse than a loud failure.

---

### Step 0.4 — Settings & Secrets Management

Write a `Settings` class using Pydantic `BaseSettings`. This is the only place environment variables are read in the entire application. Every other module imports settings, never reads `os.environ` directly.

Settings covers:
- Database URL (constructed from individual components, never stored as a single URL in .env)
- Redis URL
- Shopify API key, secret, store domain
- WhatsApp API credentials
- Google Sheets service account JSON path
- Slack webhook URL
- SendGrid API key
- OpenAI API key
- App environment (development / staging / production)
- Log level
- All threshold defaults (can be overridden per brand in YAML)

Write `.env.example` documenting every variable. New developers should be able to set up the project by copying `.env.example` to `.env` and filling in values — nothing undocumented.

For production: secrets live in Railway environment variables, DigitalOcean App Platform env vars, or AWS Secrets Manager. Never in the codebase, never in Docker images.

---

### Step 0.5 — Database Setup & Base Models

Set up SQLAlchemy with async support (asyncpg driver) and Alembic for migrations.

Create a `Base` model class that all database models inherit from:
- `id` — UUID primary key, generated server-side via `uuid4`
- `created_at` — timestamp with timezone, server default
- `updated_at` — timestamp with timezone, auto-updated on every write via SQLAlchemy event
- `is_deleted` — boolean, default False (soft deletes only, never hard delete operational data)

Configure connection pooling: min 5 connections, max 20 connections, connection timeout 30 seconds, query timeout 30 seconds. These are production values. The defaults will fail you under load.

Write the initial Alembic migration for the base schema. Verify that `alembic upgrade head` and `alembic downgrade base` both run cleanly. A migration that can't be rolled back is a production liability.

---

### Step 0.6 — Celery Setup & Task Queues

Configure Celery with Redis as both broker and result backend.

Define task priority queues:
- `realtime` — Shopify webhook processing, low stock alerts (highest priority, process immediately)
- `default` — inventory reconciliation, snapshot writes, Google Sheets updates
- `reports` — daily and weekly report generation (lowest priority, runs on schedule)

Configure task routing in Celery config so each queue can be served by appropriately scaled worker pools. In production, you might run 2 workers for realtime and 1 for reports — this is configured without code changes.

Production task settings:
- Task acknowledgement after execution starts (acks_late=True) — if a worker crashes mid-task, the task goes back to the queue
- Max task retries: 3 with exponential backoff (1min, 5min, 25min)
- Task time limit: 300 seconds (5 minutes) hard limit — any task running longer gets killed and retried
- Result expiry: 24 hours
- Dead letter queue: failed tasks after all retries are logged to a `failed_tasks` table for manual review

---

### Step 0.7 — Brand Configuration System

Build the YAML-based brand configuration system. This is what makes the system configurable per brand without code changes.

Create `config/bluorng.yaml` as the first brand config:

```yaml
brand:
  name: "Bluorng Clothing"
  shopify_domain: "bluorng.myshopify.com"
  timezone: "Asia/Kolkata"
  currency: "INR"

inventory:
  low_stock_threshold: 10          # units — alert when any variant drops below this
  critical_stock_threshold: 3      # units — escalated alert
  dead_stock_days: 21              # days without sale = dead stock flag
  slow_mover_velocity_threshold: 0.2  # fraction of category average velocity

reorder:
  default_lead_time_days: 7        # days to receive stock after ordering
  reorder_at_days_remaining: 14    # trigger reorder when X days of stock remain

reports:
  morning_report_time: "08:00"
  weekly_report_day: "monday"
  weekly_report_time: "07:00"
  recipients:
    whatsapp: ["+91XXXXXXXXXX"]
    email: ["founder@bluorng.com"]
  slack_channel: "#inventory-alerts"

categories:
  - name: "T-Shirts"
    skus: ["TS-*"]
    cost_multiplier: 1.0
  - name: "Hoodies"
    skus: ["HD-*"]
    cost_multiplier: 1.0
```

The config loader validates this YAML against a Pydantic schema on startup. Invalid config = refused startup with clear error. This prevents silent misconfiguration.

---

### Step 0.8 — CI/CD Pipeline

Set up GitHub Actions workflows.

**On every PR to dev or staging:**
- Install dependencies and run full test suite
- Run Ruff linter and Black formatter check (fail if code isn't formatted)
- Scan for accidentally committed secrets (using truffleHog or gitleaks)
- Build Docker image to verify no build errors
- Post test results as PR comment

**On merge to staging:**
- Run all tests
- Build and push Docker image to registry (tagged with commit SHA)
- Deploy to staging environment automatically
- Run smoke tests against staging (health check, one API call)
- Notify Slack: "Deployed to staging: [commit message]"

**On merge to main:**
- Same as staging but deploys to production
- Sentry release created and tagged
- Slack notification: "Deployed to production: [commit message]"

**Phase 0 Complete When:**
- `docker-compose up` brings all services up cleanly in under 60 seconds
- Health check returns green for all services
- A test Celery task executes, retries on simulated failure, and logs correctly
- CI pipeline runs and passes on a test PR
- Zero secrets exist in the codebase (scan passes)
- Brand YAML config loads and validates without errors

---

## PHASE 1 — Shopify Integration & Event Ingestion
**Duration: 4–5 Days**
**Goal: Receive every Shopify event reliably, validate it, normalise it, and store it — before doing anything else with it**

---

### Step 1.1 — Shopify Webhook Receiver

Build the webhook endpoint at `POST /webhooks/shopify/{topic}`.

This endpoint has exactly one job: receive, validate, acknowledge, and queue. It does not process. It does not update the database directly. It does not call any other service. It queues a Celery task and returns 200.

The reason for this architecture is non-negotiable: Shopify expects a 200 response within 5 seconds. If you don't respond in time, Shopify marks the webhook as failed and retries. If you process synchronously, a slow database write or API call will cause timeouts and duplicate processing.

HMAC validation is mandatory and runs before anything else:
- Read the `X-Shopify-Hmac-Sha256` header
- Compute HMAC-SHA256 of the raw request body using your webhook secret
- Compare using `hmac.compare_digest` (constant-time comparison to prevent timing attacks)
- If mismatch, log the attempt and return 401 immediately
- Never log the secret, never log the full payload at this stage (wait until after validation)

Idempotency handling:
- Read the `X-Shopify-Webhook-Id` header (unique per event, Shopify guarantees this)
- Check Redis for this ID with a 24-hour TTL
- If found, log "duplicate event, skipping" and return 200 (not an error — Shopify is doing its job)
- If not found, store in Redis, then queue the Celery task

---

### Step 1.2 — Event Storage Layer

Before any processing happens, store the raw event. This is your safety net.

Create `shopify_events` table:
- `id` UUID primary key
- `shopify_event_id` — the X-Shopify-Webhook-Id, unique indexed
- `topic` — e.g., "orders/created"
- `shop_domain` — which store sent this
- `occurred_at` — timestamp from Shopify payload
- `raw_payload` — JSONB, full original payload
- `processing_status` — enum: received, processing, completed, failed
- `processed_at` — when processing completed
- `error_message` — if failed, what went wrong
- `retry_count` — how many times processing was attempted

This table is append-only. Status is updated, but the original raw payload is never modified. If something goes wrong 3 days from now, you can reprocess any event from the beginning.

Index on: `shopify_event_id` (unique), `topic`, `processing_status`, `occurred_at`.

---

### Step 1.3 — Event Normalisation

Shopify payloads are messy. Different topics have different structures. Build a normalisation layer that converts each topic's payload into a clean internal schema.

Events to normalise for this system:

**orders/created and orders/updated:**
Extract: order_id, order_number, created_at, status, line_items (variant_id, sku, quantity, price), total_price, customer_id, fulfilment_status, cancel_reason.

**orders/cancelled:**
Extract: order_id, cancelled_at, cancel_reason, refund_status, line_items to restore to inventory.

**orders/fulfilled:**
Extract: order_id, fulfilled_at, line_items fulfilled, tracking numbers.

**inventory_levels/update:**
Extract: inventory_item_id, location_id, available (current stock level), updated_at.

**products/update:**
Extract: product_id, title, variants (variant_id, sku, price, inventory_quantity), updated_at.

Each normaliser is a pure function that takes a raw dict and returns a typed Pydantic model. Pure functions are trivially testable. Write a test for every normaliser using recorded real Shopify payloads as fixtures.

---

### Step 1.4 — Shopify REST API Client

Build the API client for pulling data from Shopify proactively (for backfill and scheduled pulls).

Shopify REST API rate limits: 2 requests/second (standard plan), 4 requests/second (Shopify Plus). Build a rate limiter that respects this using a token bucket algorithm.

Production requirements:
- Retry on 429 (rate limited): wait for the `Retry-After` header value, then retry
- Retry on 503 (Shopify maintenance): exponential backoff, max 3 retries
- Retry on network errors: exponential backoff, max 3 retries
- Circuit breaker: if 5 consecutive requests fail, stop making requests for 60 seconds and alert
- All requests logged with: endpoint, response time, status code, rate limit remaining
- Pagination handled automatically — always retrieve all pages, not just the first

Methods needed for Phase 1:
- `get_orders(since_id=None, status='any', limit=250)` — paginated
- `get_inventory_levels(inventory_item_ids)` — batch
- `get_products(since_id=None, limit=250)` — paginated
- `get_inventory_items(ids)` — batch

---

### Step 1.5 — Webhook Registration Script

Write a script `scripts/register_webhooks.py` that programmatically registers all required webhooks with Shopify.

Topics to register:
- `orders/created`
- `orders/updated`
- `orders/cancelled`
- `orders/fulfilled`
- `inventory_levels/update`
- `products/update`

Script is idempotent — check existing webhooks first, only create ones that don't exist. Output a summary of what was created vs already existed.

Include a corresponding `scripts/deregister_webhooks.py` that cleanly removes all registered webhooks. Useful when offboarding a brand or changing webhook URLs.

---

### Step 1.6 — Historical Backfill Script

Write `scripts/backfill_shopify.py` that pulls historical order and inventory data for the past N days.

The script uses the same normalisation pipeline as webhooks — data goes through identical processing regardless of source.

Production requirements:
- Resumable: store progress checkpoint in Redis. If the script fails on page 47 of orders, it resumes from page 47, not page 1.
- Rate-limit aware: uses the same API client with rate limiting
- Dry-run mode: `--dry-run` flag processes and logs but writes nothing to the database
- Progress reporting: logs percentage complete every 10% and estimated time remaining
- Conflict handling: if an order already exists, update it rather than fail

---

### Step 1.7 — Integration Tests for Shopify Layer

Write integration tests using recorded Shopify payloads as fixtures (VCR.py to record real responses once, replay forever).

Test coverage:
- Valid webhook with correct HMAC → returns 200, event stored, Celery task queued
- Invalid HMAC → returns 401, nothing stored, nothing queued
- Duplicate event ID → returns 200, processed exactly once
- All 6 event topics normalise correctly to expected schema
- Failed processing → event status updated to 'failed', error_message populated
- Backfill script completes for a 30-day window without errors
- API client correctly paginates and returns all results
- API client retries correctly on 429 and backs off

**Phase 1 Complete When:**
- All 6 webhook topics receive, validate, normalise, and store correctly
- Duplicate events handled idempotently (verified with test sending same payload twice)
- 30-day historical backfill completes successfully on test Shopify store
- All integration tests pass with zero mocked shortcuts

---

## PHASE 2 — Inventory Reconciliation Engine
**Duration: 5–6 Days**
**Goal: Accurate daily inventory reconciliation that runs automatically and requires zero human input**

---

### Step 2.1 — Core Inventory Data Models

Create the internal inventory data models. These are separate from the Shopify raw event storage.

`products` table:
- `id` UUID, `shopify_product_id`, `title`, `product_type`, `vendor`
- `category` (from YAML config mapping), `cost_price` (if available)
- `created_at`, `updated_at`

`variants` table:
- `id` UUID, `shopify_variant_id`, `product_id` (FK), `sku`, `title`
- `size`, `colour` (extracted from variant title)
- `price`, `compare_at_price`, `weight`
- `created_at`, `updated_at`

`inventory_levels` table:
- `id` UUID, `variant_id` (FK), `shopify_inventory_item_id`
- `available` (current stock count), `committed` (orders placed but not fulfilled)
- `on_hand` (available + committed), `incoming` (pending purchase orders)
- `location_id`, `shopify_location_id`
- `last_synced_at`, `created_at`, `updated_at`

`inventory_snapshots` table (the core of reconciliation):
- `id` UUID, `variant_id` (FK), `snapshot_date` (date only, not datetime)
- `opening_stock`, `units_sold`, `units_returned`, `units_adjusted`
- `closing_stock`, `sell_velocity_7d`, `sell_velocity_30d`
- `days_of_stock_remaining`, `reorder_recommended` (boolean)
- `snapshot_generated_at`

Index `inventory_snapshots` on: `variant_id` + `snapshot_date` (unique composite), `snapshot_date`.

---

### Step 2.2 — Daily Reconciliation Job

This is the central Celery task. It runs daily at a configurable time (default: 2am — after any late night orders, before the morning report).

Task: `tasks.reconciliation.run_daily_reconciliation`

Steps executed by the task:
1. Pull all orders from the previous 24 hours via Shopify API
2. Compute units sold per variant from those orders
3. Pull current inventory levels from Shopify for all variants
4. For each variant, calculate: opening stock = yesterday's closing stock, units sold from today's orders, closing stock = current Shopify inventory level
5. Compute 7-day and 30-day sell velocity (units sold / days in window)
6. Compute days of stock remaining = closing stock / 7-day velocity (handle zero velocity: null, not division error)
7. Write `inventory_snapshot` record for each variant for today's date
8. Update `inventory_levels` table with current figures
9. Run alert checks (Phase 3 handles the actual sending)
10. Log summary: total variants processed, any failures, time taken

The task must be idempotent. If it runs twice for the same day, the second run updates the existing snapshot rather than creating a duplicate. Use `ON CONFLICT DO UPDATE` at the database level.

Handle edge cases:
- Variant with zero sales in the window → velocity = 0, days remaining = null (infinite, not error)
- New variant added today → no opening stock from yesterday, use Shopify current level as both opening and closing
- Cancelled orders → subtract from units sold (don't count cancelled as real sales)
- Partially fulfilled orders → count only fulfilled units

---

### Step 2.3 — Sell Velocity Calculation Engine

Build the velocity calculation as a standalone service (not embedded in the reconciliation task). This separation allows it to be tested independently and reused by the reorder engine.

Velocity calculations:
- `velocity_7d` — units sold in last 7 days / 7
- `velocity_30d` — units sold in last 30 days / 30
- `velocity_weekday` — average units sold on weekdays (Mon–Fri)
- `velocity_weekend` — average units sold on weekends (Sat–Sun)
- `velocity_trend` — is velocity increasing or decreasing? (compare last 7d to prior 7d)

Store all five on the snapshot record. Use 30d velocity as the primary metric for reorder calculations (more stable). Use 7d velocity for alert calculations (more responsive to recent changes).

The velocity engine queries the `inventory_snapshots` table for historical data. This makes it self-contained and fast — no repeated Shopify API calls for historical analysis.

---

### Step 2.4 — Google Sheets Auto-Update

Build the Google Sheets integration that replicates the daily snapshot into the founder's existing spreadsheet — automatically.

Use the `gspread` library with a service account (not OAuth — service accounts don't require interactive login and work in automated environments).

Sheet structure to write:

**Sheet 1: "Daily Snapshot"** (cleared and rewritten daily)
- Columns: SKU, Product Name, Size, Colour, Opening Stock, Units Sold Today, Closing Stock, 7d Velocity, Days Remaining, Status (🟢 Healthy / 🟡 Low / 🔴 Critical / ⚫ Dead)

**Sheet 2: "Reorder List"** (variants needing reorder, cleared and rewritten daily)
- Columns: SKU, Product Name, Current Stock, Daily Velocity, Days Remaining, Suggested Reorder Qty, Priority (High/Medium/Low)

**Sheet 3: "Dead Stock"** (variants with zero velocity, appended weekly)
- Columns: SKU, Product Name, Last Sale Date, Units Remaining, Capital Tied Up (₹), Days Dead, Recommended Action

Write operations are batched — one API call per sheet update, not one call per row. This keeps within Google Sheets API rate limits and makes updates fast.

If the write fails (network error, quota exceeded), retry with backoff. Never skip a write silently.

---

### Step 2.5 — Inventory Snapshot API Endpoints

Build internal API endpoints that the dashboard (Phase 5) and other services consume.

`GET /api/inventory/snapshot/today` — today's full snapshot
`GET /api/inventory/snapshot/{date}` — snapshot for a specific date
`GET /api/inventory/variants/{variant_id}/history` — 30-day history for one variant
`GET /api/inventory/health` — summary: counts of healthy / low / critical / dead variants
`GET /api/inventory/low-stock` — all variants below low stock threshold
`GET /api/inventory/dead-stock` — all variants meeting dead stock criteria

All endpoints are authenticated (internal API key, not public). All responses are paginated where appropriate. All queries hit the `inventory_snapshots` table, not the live Shopify API.

---

### Step 2.6 — Tests for Reconciliation Engine

Test coverage required:
- Reconciliation job produces correct snapshot for known order set (calculate expected values manually, verify against output)
- Idempotency: running reconciliation twice for same day produces one snapshot, not two
- Cancelled orders excluded from units sold correctly
- Velocity calculation correct for variants with 0 sales, 1 sale, and many sales
- Days remaining calculated correctly at different velocity levels
- Division by zero handled gracefully (zero velocity variant)
- Google Sheets write called with correct data (mock the gspread client)
- Google Sheets write failure triggers retry

**Phase 2 Complete When:**
- Daily reconciliation job runs end-to-end with real Shopify test store data
- Google Sheet updates automatically after reconciliation runs
- Snapshot API endpoints return correct data
- All tests pass

---

## PHASE 3 — Alert & Reorder Intelligence Engine
**Duration: 4–5 Days**
**Goal: The right person gets the right alert at exactly the right moment, automatically**

---

### Step 3.1 — Alert Data Model

Create `alerts` table:
- `id` UUID, `variant_id` (FK), `alert_type` (enum), `severity` (enum: info / warning / critical)
- `triggered_at`, `acknowledged_at`, `acknowledged_by`
- `message` (human-readable alert text), `metadata` (JSONB — additional context)
- `delivered_whatsapp`, `delivered_slack`, `delivered_email` (boolean flags)
- `delivery_error` (if delivery failed)

Alert types (enum): `low_stock`, `critical_stock`, `stockout`, `dead_stock`, `slow_mover`, `reorder_due`, `reorder_overdue`.

Index on: `variant_id`, `alert_type`, `triggered_at`, `acknowledged_at`.

Do not create duplicate alerts. Before creating a new `low_stock` alert for a variant, check if one already exists that hasn't been acknowledged. If it has, update the existing alert rather than creating a new one.

---

### Step 3.2 — Alert Detection Engine

Build the alert detection service that runs after each daily reconciliation. It reads the fresh snapshot data and determines what alerts to fire.

Detection logic per variant:

**Low stock alert:** `closing_stock <= low_stock_threshold` AND `closing_stock > critical_stock_threshold` AND no unacknowledged low_stock alert exists for this variant.

**Critical stock alert:** `closing_stock <= critical_stock_threshold` AND `closing_stock > 0` AND no unacknowledged critical_stock alert exists.

**Stockout alert:** `closing_stock == 0`. Always fire, regardless of existing alerts.

**Dead stock alert:** `velocity_30d == 0` AND `last_sale_date` is more than `dead_stock_days` ago (from brand config). Fire once, then weekly if unresolved.

**Slow mover alert:** `velocity_7d < (category_average_velocity_7d * slow_mover_threshold)`. Fires weekly, not daily.

**Reorder due alert:** `days_of_stock_remaining <= lead_time_days` (from brand config). This is the most critical alert — it fires before stockout is even close.

All detection logic reads from the database, never from live Shopify API. Fast and reliable.

---

### Step 3.3 — WhatsApp Alert Delivery

Build the WhatsApp delivery service using the 360dialog or Wati API.

WhatsApp message templates must be pre-approved by Meta. Build and submit templates for:
- Low stock alert template
- Critical/stockout alert template
- Morning report template
- Reorder recommendation template

Template approval takes 24–48 hours. Submit them on Day 1 of Phase 3 while building the delivery code.

For non-template messages (replies, interactive buttons), use the WhatsApp Business API session messaging.

Delivery service requirements:
- Retry on failure: 3 attempts with 5-minute intervals
- If all retries fail, mark `delivered_whatsapp = false` and `delivery_error = error message`
- Never silently drop a message
- Rate limiting: WhatsApp Business API limits message rate — build a queue if needed
- Message deduplication: don't send the same alert twice within 1 hour

Alert message format for low stock:
```
⚠️ Low Stock Alert — Bluorng
Product: Acid Wash Hoodie (Black, M)
Current Stock: 8 units
Daily Velocity: 2.3 units/day
Days Remaining: ~3 days
Action: Reorder now — lead time is 7 days
```

---

### Step 3.4 — Slack Alert Delivery

Build the Slack delivery service using Incoming Webhooks.

Slack is for the internal team. WhatsApp is for the founder. They serve different audiences and receive different alerts:

- Founder (WhatsApp): low stock, critical stock, stockout, morning report
- Team (Slack): all of the above + dead stock, slow movers, reorder recommendations

Slack message format uses Block Kit for structured, readable alerts. Each alert includes an "Acknowledge" button that marks the alert as acknowledged in the database (via a slash command or interactive component endpoint).

If Slack is down, log the failure and move on. Slack alerts are useful, not critical. WhatsApp alerts for stockout are critical.

---

### Step 3.5 — Reorder Intelligence Engine

Build the reorder recommendation engine that tells the brand exactly what to order and how much.

Input: current snapshot data for all variants.

Output per variant needing reorder:
- SKU and product name
- Current stock level
- Days of stock remaining
- Recommended reorder quantity
- Urgency: High (< lead_time / 2), Medium (< lead_time), Low (approaching threshold)

Reorder quantity calculation:
- Target stock level = (lead_time_days + 14) × velocity_30d (2 weeks of safety stock beyond lead time)
- Reorder quantity = target_stock - current_stock
- Round up to nearest supplier minimum order quantity (configurable in YAML per supplier)

Generate a reorder summary message that can be sent directly to the supplier on WhatsApp:

```
Reorder Request — Bluorng Clothing
Date: 17 Feb 2026

Please arrange the following:
• Acid Wash Hoodie — Black/M: 50 units
• Acid Wash Hoodie — Black/L: 30 units
• Classic Tee — White/XL: 60 units

Total SKUs: 3
Required by: 24 Feb 2026 (7-day lead time)

Please confirm receipt and estimated delivery date.
```

The message is generated, stored, and shown in the dashboard for one-click sending. It is never auto-sent to the supplier without human confirmation — this is a business decision with financial consequences.

---

### Step 3.6 — Drop Performance Tracker

Build the drop launch monitoring feature for when a brand launches a new product collection.

A "drop" is defined in the brand config or created via API. On drop launch day:
- Every hour, pull sales data for all variants in the drop
- Calculate sell-through rate: units sold / total available × 100%
- Compare to expected sell-through based on historical drop performance
- Send hourly update to founder's WhatsApp on launch day only

Alert thresholds for drop performance:
- Under 10% sell-through after 4 hours → send alert: "Drop underperforming — consider pushing on Stories"
- Over 50% sell-through in first 2 hours → send alert: "Drop selling fast — check stock for top SKUs"

Drop tracking automatically deactivates after 72 hours post-launch.

---

### Step 3.7 — Tests for Alert Engine

Test coverage:
- Low stock alert fires when threshold crossed, not before
- Critical stock alert fires at correct threshold
- No duplicate alerts for same variant within cooldown period
- Stockout alert fires even if low stock alert already exists
- Dead stock alert fires only after configurable days of zero velocity
- Reorder recommendation calculates correct quantity for known velocity
- WhatsApp delivery failure triggers retry
- Retry failure marks delivery_error correctly
- Drop tracker sends hourly updates during active window only

**Phase 3 Complete When:**
- Simulated low stock scenario triggers WhatsApp alert within 5 minutes of reconciliation
- Reorder recommendation generates correct quantities for test variants
- No duplicate alerts generated in 24-hour test run

---

## PHASE 4 — Intelligence Reports
**Duration: 4–5 Days**
**Goal: The morning report lands in the founder's WhatsApp automatically every day. The weekly report lands in email every Monday. Zero manual work.**

---

### Step 4.1 — Morning Report Generator

The morning report is the most visible daily output of the system. It must be reliable, accurate, and genuinely useful — not a data dump.

Celery beat task: runs daily at the configured time (default: 8am brand timezone). Uses APScheduler for timezone-aware scheduling.

Morning report content:

**Section 1 — Yesterday's Performance**
- Total orders yesterday, total revenue
- vs same day last week (directional arrow and percentage)
- Top 3 SKUs by units sold yesterday

**Section 2 — Inventory Health**
- Count: Healthy / Low stock / Critical / Stockout / Dead
- Any new alerts since yesterday's report

**Section 3 — Action Required Today**
- List of variants needing reorder (days remaining < lead time)
- List of new stockouts
- Any critical alerts unacknowledged for more than 24 hours

**Section 4 — Weekly Trend** (Mondays only)
- "This week tracked X% vs last week"
- Top performing category

The report is generated as text for WhatsApp and as HTML for email. The same data object drives both renderers.

GPT-4o-mini writes the "Action Required" section in natural language. Input: structured data. Output: 2–3 sentences telling the founder exactly what to do today, in plain English. Brand voice from YAML config applied to the prompt.

---

### Step 4.2 — Weekly BI Report Generator

The weekly report is more comprehensive than the morning report. It's the document the founder reviews each Monday to understand the business.

Celery beat task: runs every Monday at 7am (before the morning report runs).

Report structure:

**Section 1 — Week Summary**
Revenue, orders, units sold, new customers — vs prior week and vs 4-week average.

**Section 2 — Inventory Performance**
Sell-through rates by category. Top 10 fastest moving SKUs. Dead stock list with capital-at-risk calculation. Variants that ran out this week (missed revenue opportunity).

**Section 3 — Reorder Intelligence**
Full reorder list with quantities and urgency. Suppliers to contact this week.

**Section 4 — Drop Analysis** (if any drops launched this week)
Sell-through rate, revenue generated, comparison to previous drops.

**Section 5 — Trends & Recommendations**
GPT-4o generated. 3–5 specific, actionable recommendations based on the week's data. Not generic advice. Data-driven: "Your hoodie category sold 38% faster than tees this week — your next drop should weight hoodies more heavily."

The report is rendered as:
- Clean HTML email via SendGrid
- PDF attachment (using ReportLab) also attached to the email
- Summary posted to Slack #inventory-alerts channel

---

### Step 4.3 — Report Storage & History

Store every generated report for retrieval.

`reports` table:
- `id` UUID, `report_type` (daily_morning / weekly_bi), `generated_at`
- `period_start`, `period_end`
- `content_json` (raw data that produced the report — JSONB)
- `rendered_whatsapp_text`, `rendered_html`
- `pdf_storage_path` (S3 path)
- `delivered_at`, `delivery_status`

Reports are never deleted. They're the audit trail of system operation and the historical record of business performance.

The dashboard (Phase 5) uses this table to show report history and allow re-downloading past reports.

---

### Step 4.4 — Report Delivery Reliability

Reports are business-critical. If the morning report doesn't arrive, the founder notices immediately.

Delivery reliability requirements:
- WhatsApp delivery: 3 retry attempts if initial send fails, 5-minute intervals
- Email delivery: 3 retry attempts if SendGrid returns error
- If all deliveries fail: alert to a backup channel (Slack to a #system-alerts channel)
- Monitor report delivery time: if the 8am report hasn't sent by 8:15am, trigger an immediate system alert
- Never deliver a report with incomplete or null data — validate completeness before sending

Implement a delivery confirmation check: 10 minutes after scheduled send, verify the `delivered_at` field is populated. If not, trigger retry and alert.

---

### Step 4.5 — Tests for Reports

Test coverage:
- Morning report generates with all 4 sections populated for known data set
- Report generates correctly when there are zero alerts
- Report generates correctly when there are multiple critical alerts
- GPT-4o section is validated: not empty, not exceeding character limit, no hallucinated product names
- WhatsApp delivery failure triggers retry
- Weekly report PDF renders without errors
- Report stored correctly in database after generation
- Delivery confirmation check triggers retry when delivery_at is null after 15 minutes

**Phase 4 Complete When:**
- Morning report delivered to test WhatsApp number automatically on schedule for 3 consecutive days
- Weekly report generates, renders as PDF, and delivers via email
- All tests pass

---

## PHASE 5 — Dashboard & Monitoring
**Duration: 3–4 Days**
**Goal: Full visibility into system health and inventory status — for both the internal team and the brand founder**

---

### Step 5.1 — Sentry Integration

Integrate Sentry across all services before anything goes to production.

Configure:
- Every unhandled exception captured with full stack trace, request context, user context
- Performance monitoring enabled — track slow endpoints (> 1s) and slow Celery tasks (> 30s)
- Alerts route to Slack #system-alerts immediately for any `fatal` or `error` level event
- Release tracking: tag each deployment as a Sentry release so you can see if an error started after a specific deploy
- Ignore noise: filter out expected 404s, health check logs, connection resets

Set up Sentry alerts:
- Any new error type → immediate Slack notification
- Error rate > 1% of requests → immediate Slack notification
- Celery task failure rate > 5% → immediate Slack notification

---

### Step 5.2 — Internal Operations Dashboard

Build a simple internal ops dashboard for the Module Labs team. This is not for the client — it's for you to monitor the system.

Tech: Simple React app or a Grafana dashboard (Grafana is faster to build for this use case).

Panels:
- **Event Feed**: last 50 Shopify events received with status (completed / failed / processing)
- **Reconciliation Status**: last run time, duration, variants processed, any failures
- **Alert Queue**: all active unacknowledged alerts with age
- **Report Status**: last morning report sent at, delivery status, last weekly report
- **System Health**: all services green/yellow/red (app, worker, beat, postgres, redis)
- **Failed Tasks**: list of Celery tasks that exhausted all retries, with retry button
- **API Health**: Shopify API call success rate and average latency over last 24 hours

Failing tasks must be retryable from this dashboard without touching the database or terminal. This is a production support requirement.

---

### Step 5.3 — Client-Facing Inventory Portal

Build the simple client-facing portal for the Bluorng team to view their data.

Auth: Email + password, single account per brand. JWT tokens, 24-hour expiry. No complex RBAC needed for single brand.

Pages:

**Dashboard (home):**
Today's inventory health summary. Count of healthy / low / critical / dead variants. Today's revenue and orders. Any active alerts.

**Inventory:**
Full variant list with current stock, velocity, days remaining, and status indicator. Filterable by category, status, SKU search. Sortable by days remaining (ascending = most urgent).

**Alerts:**
All alerts with acknowledge button. Filter by type and severity. Alert history for last 30 days.

**Reports:**
List of all morning reports and weekly reports with date. Click to view full report. Download PDF for weekly reports.

**Reorder:**
Current reorder recommendations with one-click copy of supplier message.

Frontend: React with Tailwind. Keep it simple. The founder needs to understand it in 30 seconds without any training.

---

### Step 5.4 — System Health Metrics

Expose Prometheus metrics from the application for monitoring.

Key metrics:
- `webhook_received_total` — counter, labelled by topic
- `webhook_processing_duration_seconds` — histogram
- `reconciliation_duration_seconds` — histogram
- `reconciliation_variants_processed` — gauge
- `alerts_triggered_total` — counter, labelled by alert_type
- `report_generation_duration_seconds` — histogram
- `celery_queue_depth` — gauge, per queue
- `shopify_api_request_duration_seconds` — histogram
- `shopify_api_errors_total` — counter

Set up alerts:
- Celery queue depth > 500 for more than 10 minutes → Slack alert
- Webhook processing latency p99 > 3s → Slack alert
- Reconciliation not completed within 30 minutes of scheduled time → Slack alert

---

### Step 5.5 — Structured Logging & Log Management

Set up log aggregation. All logs from all services (app, worker, beat) ship to a central location.

For single brand deployment: Papertrail or Logtail. Affordable, simple, searchable.

Log retention: 30 days minimum.

Set up saved searches for common debugging needs:
- All events for a specific variant SKU
- All failed Celery tasks in last 24 hours
- All WhatsApp delivery failures
- All Shopify API errors

Every log entry must include `variant_id` or `sku` when processing inventory data, so you can filter by product when a client reports an issue.

**Phase 5 Complete When:**
- Sentry capturing all errors from all services
- Internal ops dashboard shows real system data
- Client portal accessible and showing real Bluorng data
- Log search can find any variant's event history within 10 seconds

---

## PHASE 6 — End-to-End Testing, Hardening & Production Launch
**Duration: 3–4 Days**
**Goal: Ship to production with full confidence that nothing breaks under real-world conditions**

---

### Step 6.1 — Full E2E Test Suite

Write end-to-end tests that simulate complete real-world scenarios.

Scenario 1 — New drop launch:
Products added to Shopify → variants appear in inventory → opening stock set correctly → sales come in → reconciliation runs → velocity calculates → sell-through rate appears in dashboard → hourly drop updates send to WhatsApp.

Scenario 2 — Gradual stock depletion:
Variant starts at 50 units → sells 5/day → day 8: hits low stock threshold → alert fires to WhatsApp → continues selling → day 9: hits critical threshold → critical alert fires → day 10: hits zero → stockout alert fires.

Scenario 3 — Dead stock detection:
Variant has 30 units → zero sales for 21 days → dead stock alert generated → appears in Google Sheet dead stock tab → appears in weekly report dead stock section.

Scenario 4 — Reorder recommendation:
Variant at 20 units, velocity 2/day, lead time 7 days → system calculates 10 days remaining → triggers reorder alert (< 14 days) → reorder message generated → appears in client portal.

Scenario 5 — Report delivery:
Morning report generates at configured time → delivered to WhatsApp → stored in database → visible in client portal reports page.

All scenarios run against a clean test database with seeded data. All external calls mocked except Shopify (use a Shopify development store for realistic integration tests).

---

### Step 6.2 — Load Testing

Simulate peak D2C conditions using Locust.

Scenarios:
- 200 Shopify webhooks arriving in 60 seconds (sale event storm)
- Daily reconciliation running while 100 concurrent webhooks are received
- 20 concurrent users accessing the client portal

Targets:
- Webhook endpoint p99 response < 200ms (just acknowledge + queue)
- Celery queue clears within 15 minutes of a 200-event burst
- Reconciliation completes within 10 minutes for a store with 500 variants
- Portal API p99 response < 500ms

If any target is missed, identify the bottleneck. Common fixes: add database indexes, increase Celery worker count, add Redis caching for frequently-read inventory data.

---

### Step 6.3 — Security Checklist

Go through this before every production deployment:

- All API endpoints require authentication except webhook receivers (which use HMAC)
- Shopify HMAC verification cannot be bypassed under any code path
- Database user has only SELECT/INSERT/UPDATE permissions — no DROP, no CREATE
- All API keys and secrets are in environment variables, not in code or git history
- No customer or brand data appears in logs (mask email, phone numbers)
- SQL injection not possible: SQLAlchemy parameterized queries everywhere (verify with grep for raw SQL strings)
- Rate limiting on all public endpoints (prevent brute force on login)
- HTTPS enforced in production, HTTP redirects to HTTPS
- WhatsApp API credentials are restricted to this application's IP in the provider dashboard
- Google Sheets service account has access only to the brand's specific spreadsheet

---

### Step 6.4 — Operational Runbook

Write this before going live. Not after the first incident.

Document:
- How to restart each service safely
- How to check Celery queue health and identify stuck tasks
- How to manually trigger the daily reconciliation outside of schedule
- How to manually trigger a morning report send
- How to pause all alerts for a specific variant (e.g., brand knows about stockout, doesn't want alerts)
- How to add a new product category to the YAML config
- How to roll back a deployment
- What each Sentry alert means and the first 3 steps to diagnose it
- How to safely connect to the production database for read-only queries
- Brand onboarding checklist (for when you add Brand 2)

---

### Step 6.5 — Staging Deployment & Manual UAT

Deploy the complete system to a staging environment identical to production.

Connect staging to:
- A Shopify development store with realistic product catalog and order history
- A WhatsApp sandbox number
- A staging Google Sheet
- A staging Slack channel

Manual test checklist to run in staging:
- Register webhooks → place a test order → verify event received and stored
- Run reconciliation manually → verify Google Sheet updates → verify dashboard reflects new data
- Reduce a variant's stock below threshold manually → verify WhatsApp alert arrives within 5 minutes
- Trigger morning report manually → verify WhatsApp message received with correct data
- Log in to client portal → verify all data is accurate → verify all pages load without errors
- Check Sentry is receiving events from staging environment
- Check Grafana (or logging dashboard) is showing staging metrics

Do not deploy to production until every item on this checklist is checked off.

---

### Step 6.6 — Production Deployment

Deploy using the CI/CD pipeline. Never deploy manually to production.

Deployment sequence:
1. Merge to main triggers GitHub Actions
2. Tests run — if any fail, deployment stops
3. Docker image built and pushed to registry
4. Database migrations run (`alembic upgrade head`) — zero-downtime migration required
5. New containers deployed (rolling update — one at a time, health check before proceeding)
6. Verify health check endpoint returns green
7. Register Shopify webhooks for Bluorng's live store
8. Run historical backfill for last 90 days
9. Verify first batch of data appears in client portal
10. Send test morning report manually and verify delivery
11. Monitor Sentry, Grafana, and Celery for 30 minutes post-deploy

Keep previous deployment available for 1 hour. If any critical issue emerges, rollback is a single command.

---

### Step 6.7 — Go-Live Monitoring (First 72 Hours)

First 3 days after production launch, actively monitor:

- Grafana / logs dashboard open at all times during business hours
- Sentry on immediate notification for any new error type
- Manually verify each morning report for the first 3 mornings
- Manually verify Google Sheet updates correctly each morning
- Check alert delivery for first real low-stock event
- Review Celery queue depth every 4 hours
- Have a direct line of communication with Bluorng team for immediate feedback

Document every issue discovered, no matter how small. These feed into bug fixes before you onboard Brand 2.

**Phase 6 Complete When:**
- All E2E scenarios pass in staging
- Load test passes within targets
- Security checklist signed off
- Manual UAT in staging passes completely
- System live in production for 72 hours with no critical issues
- Bluorng team confirms morning report is accurate and useful

---

## SUMMARY

| Phase | Focus | Duration |
|-------|-------|----------|
| Phase 0 | Foundation & Environment | 3–4 days |
| Phase 1 | Shopify Integration & Event Ingestion | 4–5 days |
| Phase 2 | Inventory Reconciliation Engine | 5–6 days |
| Phase 3 | Alert & Reorder Intelligence | 4–5 days |
| Phase 4 | Intelligence Reports | 4–5 days |
| Phase 5 | Dashboard & Monitoring | 3–4 days |
| Phase 6 | Testing, Hardening & Launch | 3–4 days |
| **Total** | | **~26–33 working days** |

---

## Key Architecture Decisions — Why We Built It This Way

**Shopify as source of truth, not our database.**
We pull from Shopify and sync. We never try to maintain a parallel inventory count that might drift from Shopify. When there's a discrepancy, Shopify wins.

**Reconciliation reads from database, not live API.**
The daily reconciliation queries our `inventory_snapshots` table for historical data, not Shopify. This makes it fast, predictable, and not dependent on Shopify uptime.

**Alerts fire after reconciliation, not on raw webhook events.**
A single webhook event doesn't give you enough context to alert reliably. Running reconciliation first ensures you're alerting on complete, reconciled data — not a mid-day snapshot.

**WhatsApp for founder, Slack for team, Google Sheets for records.**
Different outputs for different audiences. The founder doesn't live in Slack. The ops team doesn't want WhatsApp messages for every alert. The accountant wants a spreadsheet.

**YAML config drives all thresholds.**
No threshold is hardcoded. When Bluorng wants to change their low-stock threshold from 10 to 15 units, it's a one-line YAML change and a redeploy — not a code change and a PR.

---

*Module Labs AI — Internal Development Document*
*AI Inventory & Operations Intelligence System — System 2*
*Single Brand Production Build — v1.0*
