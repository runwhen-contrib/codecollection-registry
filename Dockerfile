FROM python:3.11-slim-bookworm

ENV APP_HOME=/app

RUN groupadd -r runwhen && useradd --no-log-init -r -g runwhen runwhen

RUN apt-get update \
    && apt-get install tree wget unzip vim git -y --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $APP_HOME
ADD . $APP_HOME

RUN usermod -g 0 runwhen -G 0  \
    && chown -R runwhen:0 $APP_HOME\
    && chmod g=u /etc/passwd \
    && chmod -R g+w ${APP_HOME}

RUN pip install --no-cache-dir -r requirements.txt



USER runwhen
EXPOSE 8081
ENTRYPOINT ["/bin/sh", "-c", "./entrypoint.sh"]