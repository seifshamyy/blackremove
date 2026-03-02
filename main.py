from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
import tempfile
import shutil
import os
from remove_black_bg import remove_black_background

app = FastAPI(title="Remove Black Background API")

def cleanup(path: str):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

@app.post("/remove-bg")
async def remove_bg(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    threshold: int = Form(30),
    quality: int = Form(95),
    feather: bool = Form(True)
):
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, file.filename)
    output_path = os.path.join(temp_dir, f"output_{file.filename}.webp")

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result_path = remove_black_background(
            input_path=input_path,
            output_path=output_path,
            threshold=threshold,
            quality=quality,
            feather=feather
        )
        background_tasks.add_task(cleanup, temp_dir)
        return FileResponse(result_path, media_type="image/webp", filename="output.webp")
    except Exception as e:
        cleanup(temp_dir)
        return {"error": str(e)}
