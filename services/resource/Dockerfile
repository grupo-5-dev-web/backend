FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

# Install wget for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY services/shared /srv/shared
COPY services/resource/app /srv/resource/app
COPY services/resource/alembic.ini /srv/resource/alembic.ini
COPY services/resource/alembic /srv/resource/alembic
COPY services/resource/tests /srv/resource/tests

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sqlalchemy redis python-dotenv email-validator alembic httpx pytest pytest-cov httpx python-jose[cryptography] python-multipart

ENV PYTHONPATH="/srv:/srv/resource"

WORKDIR /srv/resource

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
