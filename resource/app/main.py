from fastapi import FastAPI

app = FastAPI(title="Resource Service")

@app.get("/")
def root():
    return {"message": "Resource Service ativo!"}
