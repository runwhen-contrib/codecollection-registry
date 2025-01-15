FROM python:3.11-slim-bookworm

ENV APP_HOME=/app

# Add non-root user and install utilities
RUN groupadd -r runwhen && useradd --no-log-init -r -g runwhen runwhen

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    tree wget unzip vim git bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up application directory and permissions
WORKDIR $APP_HOME
ADD . $APP_HOME

RUN usermod -g 0 runwhen -G 0 \
    && chown -R runwhen:0 $APP_HOME \
    && chmod g=u /etc/passwd \
    && chmod -R g+w ${APP_HOME}

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

USER runwhen

# Default to a shell for dev purposes
CMD ["bash"]
