# Image for the control-plane API service (NOT the sandbox base image).
# TODO: the sandbox base image is a separate, versioned artifact built by the
#       execution plane — see execution/runtime.py and AWS_SANDBOX_BASE_IMAGE.
FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .

EXPOSE 8000

# TODO: run as a non-root user; drop capabilities.
CMD ["uvicorn", "agent_workspaces.main:app", "--host", "0.0.0.0", "--port", "8000"]
