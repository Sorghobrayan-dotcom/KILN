# Hugging Face Spaces (SDK: docker) serves on 7860.
FROM python:3.12-slim

# Dependencies first: this layer is cached, so a code change redeploys in
# seconds rather than reinstalling genblaze and its provider adapters.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY static ./static
COPY examples ./examples

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PORT=7860

EXPOSE 7860

# No provider is contacted at start-up, so the container is ready as soon as
# uvicorn binds. Cold start is import time, nothing more.
CMD ["python", "-m", "kiln.main"]
