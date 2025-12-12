FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

# Install wget for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY services/shared /srv/shared
COPY services/user/app /srv/user/app
COPY services/user/alembic.ini /srv/user/alembic.ini
COPY services/user/alembic /srv/user/alembic

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sqlalchemy redis python-dotenv email-validator alembic httpx python-jose[cryptography] python-multipart passlib==1.7.4

ENV PYTHONPATH="/srv:/srv/user"

WORKDIR /srv/user

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
