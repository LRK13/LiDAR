from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
import shutil
import subprocess
import os
import json
from uuid import uuid4

app = FastAPI()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "classified_outputs"

# Ensure necessary directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.post("/classify_point_cloud/")
async def classify_point_cloud(
    file: UploadFile = File(...),
    ground: bool = Form(True),
    output_filename: str = Form(...)
):
    if not (file.filename.endswith(".las") or file.filename.endswith(".laz")):
        return JSONResponse(content={"error": "Only LAS or LAZ files are supported."}, status_code=400)

    try:
        file_id = str(uuid4())
        input_filename = f"{file_id}_{file.filename}"
        input_path = os.path.join(UPLOAD_DIR, input_filename)

        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Use provided output filename as-is
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        filters = []
        if ground:
            filters.append({"type": "filters.smrf"})

        pipeline = {
            "pipeline": [
                {"type": "readers.las", "filename": input_path},
                *filters,
                {"type": "writers.las", "filename": output_path}
            ]
        }

        with open("pipeline.json", "w") as f:
            json.dump(pipeline, f)

        result = subprocess.run(
            ["pdal", "pipeline", "pipeline.json"],
            check=True,
            capture_output=True,
            text=True
        )

        download_url = f"/download/{output_filename}"

        return {
            "message": "Ground classification successful.",
            "download_url": download_url
        }

    except subprocess.CalledProcessError as e:
        return JSONResponse(
            content={"error": f"PDAL Error: {e.stderr.strip()}"},
            status_code=500
        )
    except Exception as e:
        return JSONResponse(
            content={"error": f"Unexpected error: {str(e)}"},
            status_code=500
        )
    finally:
        if os.path.exists("pipeline.json"):
            os.remove("pipeline.json")


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')
    return JSONResponse(content={"error": "File not found."}, status_code=404)
