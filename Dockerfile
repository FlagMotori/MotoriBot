FROM python:3.11.3-alpine

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN apk add gcc python3-dev musl-dev

COPY nullctf.py .
COPY cogs .
COPY help_info.py .
COPY magic.json .
COPY config_vars.py .
COPY requirements.txt .

RUN pip install -r requirements.txt

CMD ["python", "nullctf.py"]