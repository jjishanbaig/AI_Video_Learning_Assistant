from datetime import datetime, timezone
from pathlib import Path
import mimetypes, json, traceback
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from google.genai.errors import APIError
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import Base, engine, get_db
from .models import Source, Artifact
from .schemas import YouTubeRequest, TextSourceRequest, GenerateRequest, ChatRequest, QuizRequest, FlashcardRequest, InterviewStartRequest, InterviewAnswerRequest
from .config import FRONTEND_ORIGIN, UPLOAD_DIR, MAX_UPLOAD_MB
from . import ai_service
from .ingestion import ALLOWED, VIDEO_EXTS, MIME, fetch_youtube_transcript, extract_document
from .exports import create_docx, create_pdf

Base.metadata.create_all(bind=engine)
app=FastAPI(title="AI Video Learning & Interview Assistant", version="1.0.0", description="Local-first AI study workspace")
app.add_middleware(CORSMiddleware, allow_origins=list({FRONTEND_ORIGIN,"http://127.0.0.1:5173","http://localhost:5173"}), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(APIError)
async def gemini_api_error_handler(request: Request, exc: APIError):
    if exc.code == 503:
        detail = "Gemini is temporarily experiencing high demand (503 UNAVAILABLE). Wait briefly, then try again."
        return JSONResponse(status_code=503, content={"detail":detail})
    return JSONResponse(status_code=502, content={"detail":f"Gemini request failed (HTTP {exc.code}). Please try again later."})

@app.get("/")
def root():
    return {"status":"ok", "app":app.title, "docs":"/docs", "health":"/api/health"}

@app.get("/api/health")
def health():
    return {"status":"ok", "app":"AI Video Learning & Interview Assistant", "gemini_configured": bool(ai_service.GEMINI_API_KEY and ai_service.GEMINI_API_KEY!="replace_with_your_key"), "model": ai_service.GEMINI_MODEL}

def serialize_source(s: Source):
    return {"id":s.id,"title":s.title,"source_type":s.source_type,"origin":s.origin,"content_length":len(s.content or ""),"summary":s.summary,"notes":s.notes,"created_at":s.created_at.isoformat() if s.created_at else None,"updated_at":s.updated_at.isoformat() if s.updated_at else None}
def need_source(db, source_id):
    s=db.get(Source,source_id)
    if not s: raise HTTPException(404,"Source not found")
    if not s.content: raise HTTPException(400,"This source has no extracted text yet.")
    return s
def save_artifact(db, source_id, kind, title, content):
    a=Artifact(source_id=source_id,kind=kind,title=title,content=content); db.add(a); db.commit(); db.refresh(a); return a

@app.get("/api/library")
def library(db: Session=Depends(get_db)):
    sources=db.query(Source).order_by(Source.created_at.desc()).all()
    return [serialize_source(s) for s in sources]

@app.get("/api/library/{source_id}")
def get_source(source_id:int, db:Session=Depends(get_db)):
    s=need_source(db,source_id)
    return {**serialize_source(s),"content":s.content,"artifacts":[{"id":a.id,"kind":a.kind,"title":a.title,"content":a.content,"created_at":a.created_at.isoformat() if a.created_at else None} for a in sorted(s.artifacts,key=lambda x:x.created_at or datetime.min,reverse=True)]}

@app.delete("/api/library/{source_id}")
def delete_source(source_id:int, db:Session=Depends(get_db)):
    s=db.get(Source,source_id)
    if not s: raise HTTPException(404,"Source not found")
    db.delete(s); db.commit(); return {"ok":True}

@app.post("/api/ingest/youtube")
def ingest_youtube(req:YouTubeRequest, db:Session=Depends(get_db)):
    try:
        transcript, vid=fetch_youtube_transcript(req.url)
        title=req.title or f"YouTube video {vid}"
        s=Source(title=title,source_type="youtube",origin=req.url,content=transcript); db.add(s); db.commit(); db.refresh(s)
        return {**serialize_source(s),"message":"Transcript imported successfully."}
    except ValueError as e: raise HTTPException(422,str(e))
    except Exception as e: raise HTTPException(502,f"YouTube transcript import failed: {e}")

@app.post("/api/ingest/text")
def ingest_text(req:TextSourceRequest, db:Session=Depends(get_db)):
    s=Source(title=req.title,source_type=req.source_type,origin="Pasted text",content=req.content.strip()); db.add(s); db.commit(); db.refresh(s); return serialize_source(s)

@app.post("/api/ingest/file")
def ingest_file(file:UploadFile=File(...), db:Session=Depends(get_db)):
    filename=Path(file.filename or "upload.txt").name
    ext=Path(filename).suffix.lower()
    if ext not in ALLOWED: raise HTTPException(415,"Unsupported file. Use PDF, DOCX, PPTX, TXT, MD, or a supported video such as MP4/MOV/WEBM.")
    dest=UPLOAD_DIR/f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    size=0
    try:
        with dest.open("wb") as out:
            while True:
                chunk=file.file.read(1024*1024)
                if not chunk: break
                size+=len(chunk)
                if size > MAX_UPLOAD_MB*1024*1024: raise HTTPException(413,f"File exceeds {MAX_UPLOAD_MB} MB limit.")
                out.write(chunk)
        if ext in VIDEO_EXTS:
            mime=file.content_type or MIME.get(ext) or mimetypes.guess_type(filename)[0] or "video/mp4"
            prompt=("Analyze this educational video. Produce a faithful transcript or detailed spoken-content outline with topic headings and any visible on-screen concepts. Preserve important terminology and sequence. If exact word-for-word transcription is not possible, clearly provide a detailed content outline instead. Include timestamps for major sections when possible. Do not claim exact timestamps if unavailable.")
            content=ai_service.analyze_video_file(dest,mime,prompt)
            source_type="video"
        else:
            content=extract_document(dest); source_type="document"
        if not content.strip(): raise HTTPException(422,"No readable text/content was extracted. For scanned PDFs, use OCR or upload a clearer/text-based file.")
        s=Source(title=filename,source_type=source_type,origin=filename,content=content); db.add(s); db.commit(); db.refresh(s)
        return {**serialize_source(s),"message":"File imported successfully."}
    except HTTPException: raise
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))
    except Exception as e: raise HTTPException(422,f"Could not process this file: {e}")
    finally:
        try: dest.unlink(missing_ok=True)
        except Exception: pass

@app.post("/api/sources/{source_id}/summary")
def generate_summary(source_id:int, req:GenerateRequest, db:Session=Depends(get_db)):
    if source_id != req.source_id: raise HTTPException(400,"Source ID mismatch")
    s=need_source(db,source_id)
    try:
        result=ai_service.summarize(s.content,s.title,req.length)
        s.summary=result; db.commit(); save_artifact(db,s.id,"summary","Summary",result)
        return {"source_id":s.id,"summary":result}
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.post("/api/sources/{source_id}/notes")
def generate_notes(source_id:int, req:GenerateRequest, db:Session=Depends(get_db)):
    if source_id != req.source_id: raise HTTPException(400,"Source ID mismatch")
    s=need_source(db,source_id)
    try:
        result=ai_service.make_notes(s.content,s.title,req.style)
        s.notes=result; db.commit(); save_artifact(db,s.id,"notes","Study notes",result)
        return {"source_id":s.id,"notes":result}
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.post("/api/chat")
def chat(req:ChatRequest, db:Session=Depends(get_db)):
    s=need_source(db,req.source_id)
    try: return {"answer":ai_service.chat_source(s.content,req.question,req.history),"source_id":s.id}
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.post("/api/quiz")
def make_quiz(req:QuizRequest, db:Session=Depends(get_db)):
    s=need_source(db,req.source_id)
    try:
        data=ai_service.quiz(s.content,req.count,req.difficulty)
        content=json.dumps(data,ensure_ascii=False,indent=2); save_artifact(db,s.id,"quiz","Practice quiz",content)
        return {"quiz":data}
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.post("/api/flashcards")
def make_flashcards(req:FlashcardRequest, db:Session=Depends(get_db)):
    s=need_source(db,req.source_id)
    try:
        data=ai_service.flashcards(s.content,req.count); content=json.dumps(data,ensure_ascii=False,indent=2); save_artifact(db,s.id,"flashcards","Flashcards",content)
        return {"flashcards":data}
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.post("/api/interview/start")
def interview_start(req:InterviewStartRequest, db:Session=Depends(get_db)):
    s=need_source(db,req.source_id)
    try:
        q=ai_service.interview_question(s.content,req.difficulty,req.interview_type,1,req.question_count,[])
        return {"question":q,"index":1,"total":req.question_count,"history":[]}
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.post("/api/interview/answer")
def interview_answer(req:InterviewAnswerRequest, db:Session=Depends(get_db)):
    s=need_source(db,req.source_id)
    try: return ai_service.evaluate_answer(s.content,req.question,req.answer,req.difficulty)
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.post("/api/interview/next")
def interview_next(payload:dict, db:Session=Depends(get_db)):
    source_id=int(payload.get("source_id",0)); s=need_source(db,source_id)
    index=int(payload.get("index",1)); total=int(payload.get("total",5)); difficulty=str(payload.get("difficulty","intermediate")); interview_type=str(payload.get("interview_type","technical")); history=payload.get("history",[])
    if index>total: return {"done":True}
    try: return {"question":ai_service.interview_question(s.content,difficulty,interview_type,index,total,history),"index":index,"total":total}
    except ai_service.AIUnavailable as e: raise HTTPException(503,str(e))

@app.get("/api/analytics")
def analytics(db:Session=Depends(get_db)):
    sources=db.query(Source).all(); artifacts=db.query(Artifact).all()
    types={}
    for s in sources: types[s.source_type]=types.get(s.source_type,0)+1
    return {"total_sources":len(sources),"total_artifacts":len(artifacts),"summaries":sum(1 for a in artifacts if a.kind=="summary"),"notes":sum(1 for a in artifacts if a.kind=="notes"),"quizzes":sum(1 for a in artifacts if a.kind=="quiz"),"flashcard_sets":sum(1 for a in artifacts if a.kind=="flashcards"),"sources_by_type":types,"recent_sources":[serialize_source(s) for s in sorted(sources,key=lambda x:x.created_at or datetime.min,reverse=True)[:5]]}

@app.get("/api/sources/{source_id}/export")
def export_source(source_id:int, format:str="pdf", kind:str="summary", db:Session=Depends(get_db)):
    s=need_source(db,source_id)
    content=s.summary if kind=="summary" else s.notes if kind=="notes" else s.content
    if not content: raise HTTPException(400,f"No {kind} available yet. Generate it first.")
    title=f"{s.title} - {kind.title()}"
    if format=="pdf": data=create_pdf(title,content); media="application/pdf"; ext="pdf"
    elif format=="docx": data=create_docx(title,content); media="application/vnd.openxmlformats-officedocument.wordprocessingml.document"; ext="docx"
    elif format=="md":
        from io import BytesIO
        data=BytesIO((f"# {title}\n\n"+content).encode()); media="text/markdown; charset=utf-8"; ext="md"
    else: raise HTTPException(400,"Supported export formats: pdf, docx, md")
    safe_name="".join(c if c.isalnum() or c in "-_ " else "_" for c in s.title)[:60].strip().replace(" ","_") or "study_material"
    return StreamingResponse(data,media_type=media,headers={"Content-Disposition":f'attachment; filename="{safe_name}_{kind}.{ext}"'})
