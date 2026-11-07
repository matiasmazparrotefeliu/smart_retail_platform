import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    print("----------------------------")
    return {"Hello": "World"}

@app.get("/health")
def health_check():
    return {"status": "ok"}