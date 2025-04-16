from fastapi import FastAPI, UploadFile, File, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import tempfile
import subprocess
import json
import laspy
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import matplotlib.colors as mcolors

app = FastAPI()

# === Helper to convert color names to hex ===
def color_name_to_hex(color_name):
    return mcolors.to_hex(mcolors.CSS4_COLORS.get(color_name, color_name))

# === Classification style map ===
default_classification_styles = {
    2:  ("Ground", "white"),
    3:  ("Low Vegetation", "lightgreen"),
    4:  ("Medium Vegetation", "green"),
    5:  ("High Vegetation", "darkgreen"),
    6:  ("Building", "slategray"),
    9:  ("Water", "blue")
}

# Step 1: Classify Point Cloud
@app.post("/classify_point_cloud/")
async def classify_point_cloud(file: UploadFile = File(...)):
    # Save the uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".laz") as in_temp:
        in_temp.write(await file.read())
        input_path = in_temp.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".laz") as out_temp:
        output_path = out_temp.name

    # Run PDAL classification pipeline
    pipeline_json = {
        "pipeline": [
            input_path,
            {
                "type": "filters.smrf",
                "scalar": 1.2,
                "slope": 0.2,
                "threshold": 0.45,
                "window": 16.0
            },
            {
                "type": "filters.assign",
                "assignment": "Classification[:]=0"
            },
            {
                "type": "filters.hag"
            },
            {
                "type": "filters.range",
                "limits": "Classification[2:2]"
            },
            output_path
        ]
    }

    # Save pipeline to JSON
    pipeline_path = os.path.join(tempfile.gettempdir(), "pdal_pipeline.json")
    with open(pipeline_path, 'w') as f:
        json.dump(pipeline_json, f)

    # Run PDAL
    result = subprocess.run(["pdal", "pipeline", pipeline_path], capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": "PDAL classification failed!", "details": result.stderr}
    
    return {"message": "File classified successfully!", "output_file": output_path}

# Step 2: Generate Contour Map
class ContourRequest(BaseModel):
    classifications: list
    line_width: float
    grid_spacing: float
    custom_colors: dict = {}  # Default value for custom_colors

@app.post("/generate_contour_map/")
async def generate_contour_map(file: UploadFile = File(...), request: ContourRequest = Body(...)):
    # Save the uploaded classified LAS/LAZ file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".laz") as temp_file:
        temp_file.write(await file.read())
        laz_path = temp_file.name

    las = laspy.read(laz_path)

    selected_classes = request.classifications
    custom_colors = request.custom_colors
    line_width = request.line_width
    grid_spacing = request.grid_spacing

    # Generate Contour Map
    fig, ax = plt.subplots(figsize=(20, 10), facecolor='black')
    ax.set_facecolor('black')

    for class_code in selected_classes:
        mask = las.classification == class_code
        x, y, z = las.x[mask], las.y[mask], las.z[mask]

        if len(z) < 100:
            continue

        x_range = np.arange(np.min(x), np.max(x), grid_spacing)
        y_range = np.arange(np.min(y), np.max(y), grid_spacing)
        grid_x, grid_y = np.meshgrid(x_range, y_range)
        grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
        grid_z = np.ma.masked_invalid(grid_z)

        if grid_z.mask.all():
            continue

        levels = np.arange(np.floor(np.min(z)), np.ceil(np.max(z)), 0.2)
        contours = ax.contour(grid_x, grid_y, grid_z, levels=levels,
                              colors=custom_colors.get(class_code, 'yellow'), linewidths=line_width)
        ax.clabel(contours, fmt='%.2f', colors='white', fontsize=6, inline=True)

    ax.axis('off')
    output_img_path = os.path.join(tempfile.gettempdir(), "contour_output.png")
    plt.savefig(output_img_path, dpi=300, bbox_inches='tight', pad_inches=0, facecolor='black')
    plt.close()

    # Return the image as a response
    return FileResponse(output_img_path, filename="contour_map.png", media_type="image/png")
