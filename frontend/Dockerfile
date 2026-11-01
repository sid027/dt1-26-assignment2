# Built from the repository root (see compose.yaml), because the page needs agent/ and config/.
FROM python:3.13-slim

WORKDIR /app
COPY agent/requirements.txt agent/requirements.txt
COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install --no-cache-dir -r agent/requirements.txt -r frontend/requirements.txt

COPY agent agent
COPY config config
COPY frontend frontend
RUN useradd --create-home app
USER app

ENV PYTHONUNBUFFERED=1
EXPOSE 8501
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["python", "-m", "streamlit", "run", "frontend/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false", \
     "--client.toolbarMode=minimal"]
