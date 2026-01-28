# secure-notes-rag

## Quick Summary

```text
Built a service-grade RAG backend with asynchronous document ingestion, per-user vector indexing, confidence-gated retrieval, and audit-ready logging
```
## 1. Project Overview

Secure Notes + RAG is a multi-user backend service that allows authenticated users to upload their documents and perform retrieval-augmented queries based on their data. All of these features are contained under strict user isolation, along with rate limiting and service-grade ingestion to ensure availability.

## 2. Architecture Overview

This service has the following structure:

```text
Client
  ↓ HTTPS
Reverse Proxy (Caddy)
  ↓ HTTP
FastAPI Application
  ├── Auth & RBAC
  ├── Notes API
  ├── RAG API
  ├── Rate Limiting (Redis)
  ├── Background Ingestion
  ↓
PostgreSQL (users, documents, chunks, audit logs)
```

## 3. Key Features

- A production-style REST API for users to take notes and upload their documents for retrieval-augmented querying
- JWT-based authentication with access control based on roles (`user`, `admin`)
- Strict multi-user document and query isolation by DB and index layers
- Per-user document ingestion implemented with background processing
- Retrieval-augmented querying with confidence gating and citation provision
- Rate limiting by user and IP with Redis
- Production-ready health and readiness checks

## 4. How to Run Locally

In your Python venv, run the following commands:
```bash
pip install -r requirements.txt
docker-compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```
For more details on service lifecycle and auxiliary troubleshooting, please refer to `RUNBOOK.md`

## 5. Threat Model

As an per-user note-taking and retrieval-augmented querying service, *secure-notes-rag* may face numerous security challenges. Please refer to the following table for more information.

| Threat                   | Risk                              | Mitigation                                    |
| ------------------------ | --------------------------------- | --------------------------------------------- |
| Unauthorized data access | User reads other users’ notes & documents, or even delete them | Per-user DB ownership + per-user vector index |
| Token theft              | Account takeover, masquerading                  | HTTPS, JWT expiry, secure headers             |
| Brute-force login        | Credential stuffing               | IP-based rate limiting                        |
| Resource exhaustion      | DoS via ingestion                 | Async ingestion + rate limits                 |
| Hallucinated answers     | False information                 | Confidence gating + abstention                |
| Injection attacks        | DB or API compromise              | ORM + validation                              |

