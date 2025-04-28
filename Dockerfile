# 1. Use an official lightweight Python image
FROM python:3.11-slim

# 2. Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 3. Set working directory
WORKDIR /app

# 4. Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    libspatialindex-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Install PDAL from source (version 2.6.2)
RUN wget https://github.com/PDAL/PDAL/releases/download/2.6.2/PDAL-2.6.2-src.tar.gz && \
    tar -xvzf PDAL-2.6.2-src.tar.gz && \
    cd PDAL-2.6.2-src && \
    mkdir build && cd build && \
    cmake .. && \
    make && make install && \
    ldconfig && \
    cd /app && rm -rf PDAL-2.6.2-src PDAL-2.6.2-src.tar.gz

# 6. Copy local code to container
COPY . /app

# 7. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 8. Expose the port
EXPOSE 10000

# 9. Command to run the app
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=10000"]
