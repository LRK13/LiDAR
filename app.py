import streamlit as st
import pdal
import os
import json  # Importing json module
from io import BytesIO

# Function to classify the ground using PDAL
def classify_ground(input_file_path, output_file_path):
    pipeline_json = {
        "pipeline": [
            input_file_path,
            {
                "type": "filters.smrf",  # SMRF (Simple Morphological Filter) to classify ground
                "window": 16.0,  # Adjust window size if necessary
                "slope": 0.2,    # Adjust slope if necessary
                "threshold": 0.45,  # Adjust threshold for ground classification
            },
            output_file_path
        ]
    }

    pipeline = pdal.Pipeline(json.dumps(pipeline_json))  # Using json.dumps
    pipeline.execute()

# Streamlit interface for uploading files
def main():
    st.title("LiDAR Ground Classification with PDAL")

    # File uploader
    uploaded_file = st.file_uploader("Upload LAS or LAZ file", type=["las", "laz"])

    if uploaded_file is not None:
        # Save the uploaded file
        input_file_path = os.path.join("uploads", uploaded_file.name)
        os.makedirs("uploads", exist_ok=True)
        with open(input_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Output file path
        output_file_path = os.path.join("uploads", f"classified_{uploaded_file.name}")

        # Button to classify ground
        if st.button("Classify Ground"):
            # Classify the ground points using PDAL
            classify_ground(input_file_path, output_file_path)
            st.success("Ground classification complete!")

            # Provide the classified file for download
            with open(output_file_path, "rb") as f:
                classified_file = BytesIO(f.read())
            st.download_button(
                label="Download Classified LAS/LAZ File",
                data=classified_file,
                file_name=f"classified_{uploaded_file.name}",
                mime="application/octet-stream"
            )

if __name__ == "__main__":
    main()
