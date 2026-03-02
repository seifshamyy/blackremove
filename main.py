import base64
import os
import shutil
import tempfile
import httpx

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from remove_black_bg import remove_black_background

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDqOM04OQpTAkWmbAVJxMNBnN9GEDkMYLw")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-3.1-flash-image-preview:generateContent"
)

app = FastAPI(title="NanoBanana – Black-BG Remover")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets (our frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/process")
async def process(
    file: UploadFile = File(...),
    threshold: int = Form(30),
    quality: int = Form(95),
    feather: bool = Form(True),
):
    # ── 1. Read uploaded image ─────────────────────────────────────────────────
    raw_bytes = await file.read()
    mime_type = file.content_type or "image/png"
    b64_image = base64.b64encode(raw_bytes).decode()

    # ── 2. Call Gemini to make logo white on black background ──────────────────
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Look at this logo, make it all white, put it on a black background. "
                            "That's it. Zero changes to logo vectors, color change, black background."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_image,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            GEMINI_URL,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            json=payload,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {resp.text}")

    # ── 3. Extract image from Gemini response ──────────────────────────────────
    response_data = resp.json()
    gemini_image_b64 = None
    gemini_mime = "image/png"
    try:
        for part in response_data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                gemini_image_b64 = part["inlineData"]["data"]
                gemini_mime = part["inlineData"].get("mimeType", "image/png")
                break
    except (KeyError, IndexError):
        pass

    if not gemini_image_b64:
        raise HTTPException(status_code=502, detail="Gemini returned no image.")

    gemini_image_bytes = base64.b64decode(gemini_image_b64)

    # ── 4. Save Gemini output → run remove_black_bg → return result ────────────
    tmp_dir = tempfile.mkdtemp()
    try:
        ext = ".png" if "png" in gemini_mime else ".jpg"
        intermediate = os.path.join(tmp_dir, f"gemini_out{ext}")
        with open(intermediate, "wb") as f:
            f.write(gemini_image_bytes)

        output_path = os.path.join(tmp_dir, "result.webp")
        remove_black_background(
            input_path=intermediate,
            output_path=output_path,
            threshold=threshold,
            quality=quality,
            feather=feather,
        )

        # Read the result and return it as bytes (we clean up the tmp dir ourselves)
        with open(output_path, "rb") as f:
            result_bytes = f.read()

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Return as base64 JSON so the browser can display + download it
    return JSONResponse(
        {
            "image": base64.b64encode(result_bytes).decode(),
            "mime": "image/webp",
        }
    )
