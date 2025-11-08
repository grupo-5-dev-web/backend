from fastapi import FastAPI

app = FastAPI(title="Reservation Service")

@app.get("/")
def root():
    return {"message": "Reservation Service ativo!"}
