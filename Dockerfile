# The explorer for developers: Python, Java (Beagle) and the code, with the data and the reference panel mounted from
# the host (compose.yaml). Personal data never goes into the image (.dockerignore).
FROM python:3.10-slim-bookworm

# Java for Beagle (imputation); the reference files themselves are mounted, not copied
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The code, so the image runs on its own too; compose mounts the working copy over it for live edits
COPY . .

ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    DNA_BIND_HOST=0.0.0.0

EXPOSE 8000
CMD ["python", "-m", "cluster_analysis.explorer", "serve"]
