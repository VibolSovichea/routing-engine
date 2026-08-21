from fastapi import FastAPI

from app.api.geocode import router as geocode_router

app = FastAPI()
app.include_router(geocode_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
