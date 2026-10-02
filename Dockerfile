# syntax=docker/dockerfile:1

# This Dockerfile uses Python Docker Official Image
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Server Configuration
ENV GCHAT_HOST="0.0.0.0"
ENV GCHAT_PORT="3355"
ENV GCHAT_MAX_CLIENT="256"

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

#RUN --mount=type=cache,target=/root/.cache/pip \
#    --mount=type=bind,source=requirements.txt,target=requirements.txt \
#    python -m pip install -r requirements.txt

USER appuser

# Copy the source code into the container.
COPY ./server.py ./server.py
COPY ./commands.py ./commands.py
COPY *.plugin.py ./

# Expose the port that the application listens on.
EXPOSE 3355

# Run the application.
CMD ["python3", "server.py", "--messages", "/app/var/messages.json", "--env"]
