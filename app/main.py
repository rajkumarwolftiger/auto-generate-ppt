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

# ✅ Load .env first
load_dotenv()

# ----------- App Setup ------------
app = FastAPI(title="Auto PPT Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # loosen later if needed
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Ensure folders exist
STATIC_DIR = "app/web/static"
TEMPLATE_DIR = "app/web/templates"
OUTPUT_DIR = "data/output"

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Mount static + templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# ----------- Serve Web UI ----------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve homepage"""
    return templates.TemplateResponse("index.html", {"request": request})

# ----------- API: Generate PPT ----------
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

        # Step 1: Break input into sections
        sections = map_text_to_sections(input_text, tone_hint)

        # Step 2: Generate slides
        plan = generate_slide_plan(sections, tone=tone_hint)
        slides = [refine_slide_bullets(s, tone=tone_hint) for s in plan]

        # Step 3: Optional speaker notes
        notes = maybe_notes(slides) if add_notes else None

        # Step 4: Build final PPTX
        out_name = f"auto_{uuid.uuid4().hex[:8]}.pptx"
        out_path = os.path.join(OUTPUT_DIR, out_name)
        build_presentation(template_path, slides, notes, out_path)

        return FileResponse(
            out_path,
            filename=out_name,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    except Exception as e:
        print("❌ Backend Error:", e)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ----------- API: Preview Slides ----------
@app.post("/preview")
async def preview(input_text: str = Form(...), tone_hint: str = Form("")):
    try:
        sections = map_text_to_sections(input_text, tone_hint)
        plan = generate_slide_plan(sections, tone=tone_hint)
        slides = [refine_slide_bullets(s, tone=tone_hint) for s in plan]
        return {"slides": slides}
    except Exception as e:
        print("❌ Preview Error:", e)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
