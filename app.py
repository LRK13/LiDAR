from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import shutil
import subprocess
import os
import json
from uuid import uuid4
from typing import Optional

app = FastAPI()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "classified_outputs"

# Ensure necessary directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/")
def read_root():
    return {"message": "PDAL classification API is running."}


@app.post("/classify_point_cloud/")
async def classify_point_cloud(
    file: UploadFile = File(...),
    output_filename: str = Form(...),
    ground: Optional[bool] = Form(True)  # Ground is now optional
):
    """
    Endpoint to classify point cloud data (LAS/LAZ) and extract ground points.

    Args:
        file (UploadFile): The LAS or LAZ file to process.
        output_filename (str): The desired filename for the output LAS file.
        ground (Optional[bool]): Whether to perform ground classification (default: True).

    Returns:
        JSONResponse: A JSON response containing either a download URL or an error message.
    """

    if not (file.filename.endswith(".las") or file.filename.endswith(".laz")):
        raise HTTPException(status_code=400, detail="Only LAS or LAZ files are supported.")

    try:
        file_id = str(uuid4())
        input_filename = f"{file_id}_{file.filename}"
        input_path = os.path.join(UPLOAD_DIR, input_filename)
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        filters = []
        if ground:
            filters.append({"type": "filters.smrf"})

        pipeline = {
            "pipeline": [
                {"type": "readers.las", "filename": input_path},
                *filters,
                {"type": "writers.las", "filename": output_path},
            ]
        }

        with open("pipeline.json", "w") as f:
            json.dump(pipeline, f)

        result = subprocess.run(
            ["pdal", "pipeline", "pipeline.json"],
            check=True,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                returncode=result.returncode, cmd=["pdal", "pipeline", "pipeline.json"], stderr=result.stderr
            )

        download_url = f"/download/{output_filename}"

        return {"message": "Ground classification successful.", "download_url": download_url}

    except subprocess.CalledProcessError as e:
        print(f"PDAL Error: {e.stderr.strip()}")  # Log the error
        raise HTTPException(status_code=500, detail=f"PDAL Error: {e.stderr.strip()}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Log the error
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    finally:
        if os.path.exists("pipeline.json"):
            os.remove("pipeline.json")
        # Clean up input file (regardless of success/failure)
        if os.path.exists(input_path):
            os.remove(input_path)


@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Endpoint to download a classified point cloud file.

    Args:
        filename (str): The name of the file to download.

    Returns:
        FileResponse: The classified LAS file.

    Raises:
        HTTPException: 404 if the file is not found.
    """
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")