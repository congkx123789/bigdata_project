from fastapi import FastAPI, BackgroundTasks, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uuid

from routers import chats, documents

app = FastAPI(title="Nexus Core API", version="1.0.0")

# Enable CORS for Frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chats.router)
app.include_router(documents.router)

@app.get("/")
async def root():
    return {"message": "Nexus Core API Operational", "status": "Online"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
