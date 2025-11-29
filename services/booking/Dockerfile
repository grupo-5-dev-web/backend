FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

COPY services/shared /srv/shared
COPY services/booking/app /srv/booking/app
COPY services/booking/alembic.ini /srv/booking/alembic.ini
COPY services/booking/alembic /srv/booking/alembic

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sqlalchemy redis python-dotenv email-validator alembic httpx

ENV PYTHONPATH="/srv:/srv/booking"

WORKDIR /srv/booking

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
