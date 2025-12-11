FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

COPY services/shared /srv/shared
COPY services/tenant/app /srv/tenant/app
COPY services/tenant/alembic.ini /srv/tenant/alembic.ini
COPY services/tenant/alembic /srv/tenant/alembic

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sqlalchemy redis python-dotenv email-validator alembic httpx python-jose[cryptography] python-multipart

ENV PYTHONPATH="/srv:/srv/tenant"

WORKDIR /srv/tenant

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
