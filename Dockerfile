FROM registry.gitlab.com/virtual_agents/gateway/base:latest
WORKDIR /app

COPY . .

RUN pip install --upgrade pip \
 && pip install -r requirements.txt

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]