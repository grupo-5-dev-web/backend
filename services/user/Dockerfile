FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

COPY services/shared /srv/shared
COPY services/user/app /srv/user/app

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sqlalchemy redis python-dotenv email-validator

ENV PYTHONPATH="/srv:/srv/user"

WORKDIR /srv/user

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
