# syntax=docker/dockerfile:1
FROM python:3.11
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG USER_ID_TO_SAVE_FILES
ARG GROUP_ID_TO_SAVE_FILES

# Install system dependencies
RUN apt-get update && apt-get install -y \
    supervisor \
    redis-server \
    libpq-dev \
    python3-dev \
    build-essential \
    libffi-dev \
    libssl-dev

# Create user
RUN groupadd -g ${GROUP_ID_TO_SAVE_FILES} dummy-user && \
    useradd -u ${USER_ID_TO_SAVE_FILES} -g dummy-user -m dummy-user

# Install wheel BEFORE copying the code
RUN pip install --upgrade pip && \
    pip install wheel setuptools --upgrade

WORKDIR /code
COPY . /code/
RUN mkdir -p /var/log/gunicorn && chmod 755 /var/log/gunicorn

# Now install requirements
RUN pip install --no-cache-dir -r requirements.txt && \
    cd backend_django_project && python manage.py migrate

COPY ./supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]