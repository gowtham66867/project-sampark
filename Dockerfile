FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

# Cloud Run injects PORT; run_demo.py already defaults --port to
# $PORT and --host to 0.0.0.0 (see main()), so no flags are needed here.
CMD ["python", "run_demo.py"]
