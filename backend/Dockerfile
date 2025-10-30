FROM python:3.12-slim-bullseye
WORKDIR /app
COPY ./app /app
COPY requirements.txt /app/

RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --default-timeout=180 -r requirements.txt
ENV PYTHONUNBUFFERED=1
EXPOSE 19069
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "19069"]
