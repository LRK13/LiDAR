import streamlit as st
import os
import tempfile
import subprocess
import json
import laspy
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import matplotlib.colors as mcolors

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

# === Streamlit App ===
st.set_page_config(page_title="LiDAR Classifier & Contour Generator", layout="wide")
st.title("LiDAR Classifier & Contour Generator")

step = st.radio("Choose Step", ["1. Classify Point Cloud", "2. Generate Contour Map"])

if step == "1. Classify Point Cloud":
    st.subheader("Upload an unclassified LAS/LAZ file")
    unclassified_file = st.file_uploader("Upload LAS/LAZ", type=["las", "laz"])

    if unclassified_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".laz") as in_temp:
            in_temp.write(unclassified_file.read())
            input_path = in_temp.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".laz") as out_temp:
            output_path = out_temp.name

        st.write("Running PDAL classification pipeline...")

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
            st.error("PDAL classification failed!")
            st.text(result.stderr)
        else:
            st.success("File classified successfully!")
            with open(output_path, "rb") as f:
                st.download_button("Download Classified File", f, file_name="classified_output.laz", mime="application/octet-stream")

elif step == "2. Generate Contour Map":
    st.subheader("Upload a classified LAS/LAZ file")
    uploaded_file = st.file_uploader("Upload classified LAS/LAZ", type=["las", "laz"])

    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".laz") as temp_file:
            temp_file.write(uploaded_file.read())
            laz_path = temp_file.name

        las = laspy.read(laz_path)
        st.success("File loaded!")

        unique_classes = np.unique(las.classification)
        selected_classes = st.multiselect(
            "Select classifications to include:",
            options=unique_classes,
            format_func=lambda x: f"Class {x}: {default_classification_styles.get(x, ('Unknown', 'yellow'))[0]}"
        )

        custom_colors = {}
        st.subheader("Customize contour line colors")
        for cls in selected_classes:
            label, default_color = default_classification_styles.get(cls, ("Unknown", "yellow"))
            default_color_hex = color_name_to_hex(default_color)
            user_color = st.color_picker(f"Class {cls} ({label})", default_color_hex)
            custom_colors[cls] = user_color

        line_width = st.slider("Line width", 0.1, 5.0, 0.6)
        grid_spacing = st.slider("Grid spacing (m)", 0.5, 10.0, 1.0)

        if st.button("Generate Contour Map"):
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
                                      colors=custom_colors[class_code], linewidths=line_width)
                ax.clabel(contours, fmt='%.2f', colors='white', fontsize=6, inline=True)

            ax.axis('off')
            output_img_path = os.path.join(tempfile.gettempdir(), "contour_output.png")
            plt.savefig(output_img_path, dpi=300, bbox_inches='tight', pad_inches=0, facecolor='black')
            plt.close()

            st.image(output_img_path, caption="Generated Contour Map", use_column_width=True)
            with open(output_img_path, "rb") as f:
                st.download_button("Download Contour Image", f, file_name="contour_map.png", mime="image/png")
