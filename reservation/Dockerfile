FROM python:3.11-slim

WORKDIR /reservation

COPY ./app /reservation/app

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sqlalchemy redis python-dotenv

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
