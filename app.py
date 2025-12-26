import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chatbot import CourseChatbot, load_courses
from kg import KnowledgeGraph


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

kg = KnowledgeGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)

courses = load_courses()
chatbot = CourseChatbot(courses, kg)

app = FastAPI(title="University Course Assistant Chatbot + Auto Knowledge Graph")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    text: str


@app.post("/chat")
def chat(req: ChatRequest):
    reply, intent, entities = chatbot.process(req.text)
    return {"reply": reply, "intent": intent, "entities": entities}


@app.get("/health")
def health():
    ok, error = kg.health()
    return {
        "status": "ok",
        "neo4j": "ok" if ok else "down",
        "error": error,
    }


@app.get("/graph/summary")
def graph_summary():
    ok, error = kg.health()
    if not ok:
        return {"nodes": 0, "edges": 0, "error": error}
    summary, err = kg.summary()
    if err or summary is None:
        return {"nodes": 0, "edges": 0, "error": err}
    return summary


@app.get("/graph/export")
def graph_export():
    ok, error = kg.health()
    if not ok:
        return {"nodes": [], "edges": [], "error": error}
    graph, err = kg.export_graph()
    if err or graph is None:
        return {"nodes": [], "edges": [], "error": err}
    return graph


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/graph")
def graph_page():
    return FileResponse(FRONTEND_DIR / "graph.html")


@app.on_event("shutdown")
def shutdown_event():
    kg.close()


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
