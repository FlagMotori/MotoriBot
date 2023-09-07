FROM python:3.11.3-slim

ENV NAME bot
ENV APP_HOME /home/bot

RUN groupadd -g 1000 -r ${NAME} && useradd -r -g ${NAME} -u 1000 ${NAME}

RUN apt update && apt install -y \
    gcc \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR ${APP_HOME}

RUN chown ${NAME}:${NAME} ${APP_HOME}

USER ${NAME}

#COPY --chown=${NAME}:${NAME} ./* ${APP_HOME}/
COPY --chown=${NAME}:${NAME} nullctf.py .
COPY --chown=${NAME}:${NAME} cogs ./cogs
COPY --chown=${NAME}:${NAME} help_info.py .
COPY --chown=${NAME}:${NAME} magic.json .
COPY --chown=${NAME}:${NAME} config_vars.py .
COPY --chown=${NAME}:${NAME} requirements.txt .

CMD ["python", "-u", "nullctf.py"]
