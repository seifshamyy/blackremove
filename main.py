import base64
import logging
import os
import shutil
import tempfile

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from remove_black_bg import remove_black_background

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY env variable is required. Set it in .env or export it.")

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

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/process")
async def process(
    file: UploadFile = File(...),
    threshold: int = Form(30),
    quality: int = Form(95),
    feather: str = Form("true"),   # receive as string, parse manually
):
    feather_bool = feather.lower() not in ("false", "0", "no", "off")

    # ── 1. Read uploaded image ─────────────────────────────────────────────────
    raw_bytes = await file.read()
    mime_type = file.content_type or "image/png"
    # Normalise mime type
    if mime_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        mime_type = "image/png"
    b64_image = base64.b64encode(raw_bytes).decode()

    # ── 2. Call Gemini ─────────────────────────────────────────────────────────
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

    logger.info("Calling Gemini API with mime_type=%s, data_len=%d", mime_type, len(b64_image))
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                GEMINI_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": GEMINI_API_KEY,
                },
                json=payload,
            )
    except Exception as e:
        logger.exception("HTTP request to Gemini failed")
        raise HTTPException(status_code=502, detail=f"Network error calling Gemini: {e}")

    logger.info("Gemini response status: %d", resp.status_code)

    if resp.status_code != 200:
        error_body = resp.text[:500]
        logger.error("Gemini API error: %s", error_body)
        raise HTTPException(status_code=502, detail=f"Gemini API error {resp.status_code}: {error_body}")

    # ── 3. Extract image from response ─────────────────────────────────────────
    response_data = resp.json()
    gemini_image_b64 = None
    gemini_mime = "image/png"

    try:
        for part in response_data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                gemini_image_b64 = part["inlineData"]["data"]
                gemini_mime = part["inlineData"].get("mimeType", "image/png")
                break
    except (KeyError, IndexError) as e:
        logger.error("Could not parse Gemini response: %s | response: %s", e, str(response_data)[:300])

    if not gemini_image_b64:
        # Log what Gemini said if no image
        text_parts = []
        try:
            for part in response_data["candidates"][0]["content"]["parts"]:
                if "text" in part:
                    text_parts.append(part["text"])
        except Exception:
            pass
        logger.error("Gemini returned no image. Text parts: %s", text_parts)
        raise HTTPException(status_code=502, detail=f"Gemini returned no image. Model said: {' '.join(text_parts)[:200]}")

    gemini_image_bytes = base64.b64decode(gemini_image_b64)
    logger.info("Gemini image received: mime=%s size=%d bytes", gemini_mime, len(gemini_image_bytes))

    # ── 4. Run remove_black_bg ─────────────────────────────────────────────────
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
            feather=feather_bool,
        )

        with open(output_path, "rb") as f:
            result_bytes = f.read()
    except Exception as e:
        logger.exception("Error in remove_black_background")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return JSONResponse(
        {
            "image": base64.b64encode(result_bytes).decode(),
            "mime": "image/webp",
        }
    )
