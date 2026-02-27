# Phase 0 — Foundation & Environment Setup
**Duration: 3-4 days**

## Step 0.1 — Repository Structure ✓
- [x] Create project folder
- [x] Initialize git
- [x] Create .gitignore
- [x] Create claude.md planning doc
- [x] Create phase checklist

## Step 0.2 — Docker Environment ✓
- [x] Create docker-compose.yml
- [x] Create docker-compose.prod.yml
- [x] Create Dockerfile for app
- [x] Configure postgres service with health check
- [x] Configure redis service with health check
- [x] Configure app service with dependency on postgres/redis
- [x] Configure worker service
- [x] Configure beat service
- [x] Test: docker-compose up brings all services up cleanly
- [x] Test: Health checks pass for all services

## Step 0.3 — Core Application Setup ✓
- [x] Create app/ directory structure (api, integrations, services, workers, models, schemas)
- [x] Set up FastAPI application factory (create_app())
- [x] Configure structlog for structured JSON logging (app/core/logging.py)
- [x] Add request ID middleware (app/core/middleware.py — X-Request-ID tracing)
- [x] Add global exception handler (app/core/exceptions.py)
- [x] Create health check endpoint GET /health (returns db + redis status)
- [x] Add startup validation (env var check + Postgres/Redis connectivity on lifespan startup)
- [x] Test: /health returns 200 with service status (503 when degraded)

## Step 0.4 — Settings & Secrets Management
- [ ] Create app/core/settings.py with Pydantic BaseSettings
- [ ] Create .env.example with all variables documented
- [ ] Add Settings validation on startup
- [ ] Test: Missing required var = refused startup with clear error

## Step 0.5 — Database Setup
- [ ] Install SQLAlchemy + asyncpg
- [ ] Create app/core/database.py with async engine
- [ ] Create app/models/base.py with Base model (id, created_at, updated_at, is_deleted)
- [ ] Configure connection pooling (min 5, max 20)
- [ ] Set query timeout to 30 seconds
- [ ] Install Alembic
- [ ] Initialize Alembic with async template
- [ ] Create initial migration for base schema
- [ ] Test: alembic upgrade head works
- [ ] Test: alembic downgrade base works

## Step 0.6 — Celery Setup
- [ ] Install Celery + Redis
- [ ] Create app/core/celery_app.py
- [ ] Configure task queues: realtime, default, reports
- [ ] Configure task routing
- [ ] Set acks_late=True, max_retries=3, time_limit=300s
- [ ] Configure result expiry 24 hours
- [ ] Create test task
- [ ] Test: Task executes successfully
- [ ] Test: Task retries on failure
- [ ] Test: Task logs correctly

## Step 0.7 — Brand Configuration System
- [ ] Create config/ directory
- [ ] Create config/schema.py with Pydantic schema for brand config
- [ ] Create config/bluorng.yaml with full config
- [ ] Create config loader that validates YAML on startup
- [ ] Test: Valid config loads
- [ ] Test: Invalid config refuses startup

## Step 0.8 — CI/CD Pipeline
- [ ] Create .github/workflows/test.yml (runs on PR)
- [ ] Create .github/workflows/deploy-staging.yml
- [ ] Create .github/workflows/deploy-prod.yml
- [ ] Configure: run tests, linting, format check
- [ ] Configure: scan for secrets
- [ ] Configure: build Docker image
- [ ] Test: Create test PR, verify pipeline runs

## Phase 0 Complete When:
- [ ] docker-compose up brings all services up in <60s
- [ ] Health check returns green for all services
- [ ] Test Celery task executes and logs correctly
- [ ] CI pipeline runs and passes
- [ ] Zero secrets in codebase (scan passes)
- [ ] Brand YAML loads and validates