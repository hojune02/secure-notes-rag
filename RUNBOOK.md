# RUNBOOK.md

## 1. Service lifecycle

This service requires `db` and `redis` to be live, which you can ensure by the following command:
```bash
docker-compose up -d db redis
```
You can always deactivate them using:
```bash
docker-compose down
```

## 2. Database Migrations

This service uses `alembic` for database migrations. You can generate your migrations like this:
```bash
alembic revision --autogenerate -m "your changes"
```
You can run the following command to update your migration or downgrade it upon failure:
```bash
alembic upgrade head
alembic downgrade -1
``` 

## 3. Possible Failures

When Redis is down, rate limiting is disabled but the overall service is still functional.

When DB is down, the overall service cannot access notes and documents, as well as user information. Service readiness should fail.

When document ingestion fails, the document's status on `Document` table wil be set to `failed`.

## 4. Security operations

### JWT Overview

Do NOT ever commit .env to version control, since it contains the JWT secret. JWTs are stateless, hence all valid tokens signed with the secret will be compromised until expiration if it is leaked.

#### Rotating JWT Secret

Rotating the JWT secret will immediately invalidates all existing tokens.
- Generate a new secret using `openssl`
```bash
openssl rand -base64 48
```
- Update .env
```env
JWT_SECRET=<new-secret>
```
- Restart the API service
```bash
docker-compose down
docker-compose up -d db redis
uvicorn app.main:app --reload
```

#### Token Lifetime

Token lifetime is set to 15 minutes by default in `.env` file. Changing it to short lifetime can be crucial for a security-sensitive service.

### Database Security

This service uses `sqlalchemy` for allowing only system-endorsed SQL queries to be executed. This is achieved by using ORM. 

### Audit Logging & Incident Investigation

Audit logs record events such as user login, document upload, and RAG queries. Every audit log entry includes the following:

- `action_user_id`
- `event_type`
- `details`
- `created_at`

Use the following command to query for audit logs of an user:
```sql
SELECT *
FROM audit_logs
WHERE actor_user_id = '<user-uuid>'
ORDER BY created_at DESC;
```
