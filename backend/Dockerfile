FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt
COPY *.py ./
COPY entrypoint.sh /entrypoint.sh
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
EXPOSE 8001
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
