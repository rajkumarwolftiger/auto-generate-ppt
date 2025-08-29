import os
import tempfile, shutil, uuid, traceback
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.services.llm import generate_slide_plan, refine_slide_bullets, maybe_notes
from app.services.text_mapper import map_text_to_sections
from app.services.pptx_builder import build_presentation

# ✅ Load .env before anything else
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Mount static + templates
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
templates = Jinja2Templates(directory="app/web/templates")

# ----------- Serve Web UI ----------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ----------- API to generate PPT ----------
@app.post("/generate")
async def generate(
    request: Request,
    input_text: str = Form(...),
    tone_hint: str = Form(""),
    file: UploadFile = File(...),
    add_notes: bool = Form(False)
):
    tmpdir = tempfile.mkdtemp()
    try:
        if not file.filename.lower().endswith((".pptx", ".potx")):
            raise HTTPException(status_code=400, detail="Upload a .pptx or .potx template")

        # Save uploaded template
        template_path = os.path.join(tmpdir, file.filename)
        with open(template_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 1. Map and split text
        sections = map_text_to_sections(input_text, tone_hint)

        # 2. Generate slides (using AIpipe key)
        plan = generate_slide_plan(sections, tone=tone_hint)
        slides = [refine_slide_bullets(s, tone=tone_hint) for s in plan]

        # 3. Optional notes
        notes = maybe_notes(slides) if add_notes else None

        # 4. Build presentation
        out_name = f"auto_{uuid.uuid4().hex[:8]}.pptx"
        out_path = os.path.join("data", "output", out_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        build_presentation(template_path, slides, notes, out_path)

        return FileResponse(out_path, filename=out_name,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")

    except Exception as e:
        # ✅ Print detailed error to logs + return message to frontend
        print("❌ Backend Error:", e)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

@app.post("/preview")
async def preview(
    input_text: str = Form(...),
    tone_hint: str = Form("")
):
    try:
        sections = map_text_to_sections(input_text, tone_hint)
        plan = generate_slide_plan(sections, tone=tone_hint)
        slides = [refine_slide_bullets(s, tone=tone_hint) for s in plan]
        return {"slides": slides}
    except Exception as e:
        print("❌ Preview Error:", e)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
