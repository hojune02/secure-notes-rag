# secure-notes-rag

## Quick Summary

**Built a service-grade RAG backend with asynchronous document ingestion, per-user vector indexing, confidence-gated retrieval, and audit-ready logging**

## Table of Contents
[1. Project Overview](#1-project-overview)

[2. Architecture Overview](#2-architecture-overview)

[3. Key Features](#3-key-features)

[4. How to Run Locally](#4-how-to-run-locally)

[5. Threat Model](#5-threat-model)

## 1. Project Overview

`secure-notes-rag` is a multi-user backend service that allows authenticated users to upload their documents and perform retrieval-augmented queries based on their data. All of these features are contained under strict user isolation, along with rate limiting and service-grade ingestion to ensure availability.

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
    - You need to set your JWT secret in `.env` before running this service locally. Please refer to [*Rotating JWT Secret* section of RUNBOOK.md](RUNBOOK.md#rotating-jwt-secret)
- Strict multi-user document and query isolation by DB and index layers
- Per-user document ingestion implemented with background processing
- Retrieval-augmented querying with confidence gating and citation provision
- Rate limiting by user and IP with Redis
- Production-ready health and readiness checks

## 4. How to Run Locally & with TLS

In your Python venv, run the following commands:
```bash
pip install -r requirements.txt
docker-compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```
For more details on service lifecycle and auxiliary troubleshooting, please refer to [RUNBOOK.md](RUNBOOK.md).

### TLS

This project contains a Caddyfile for running a reverse proxy with HTTPS handling. The reverse proxy sits in between clients and the API service. Run the proxy using the following command:
```bash
docker-compose up -d caddy
```

You need to copy the TLS certificate from `securenotes-caddy` onto your local device, and then anchor the certificate so that your device can trust it. For my setup (Arch Linux), the following commands worked. This may differ depending on your local environment:
```bash
docker cp securenotes-caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-local-root.crt
sudo cp ./caddy-local-root.crt /etc/ca-certificates/trust-source/anchors/
sudo update-ca-trust
```
Then, using `curl` to connect to `localhost` securely will work. Acessing the service from your browser may still not work, unless you set your browser to trust the certificate. 

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

