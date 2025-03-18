# syntax=docker/dockerfile:1
# using django development server
FROM python:3.11
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG USER_ID_TO_SAVE_FILES

ARG GROUP_ID_TO_SAVE_FILES

RUN groupadd -g ${GROUP_ID_TO_SAVE_FILES} dummy-user && \
    useradd -u ${USER_ID_TO_SAVE_FILES} -g dummy-user -m dummy-user

WORKDIR /code
COPY . /code/

RUN mkdir -p /var/log/gunicorn && chmod 755 /var/log/gunicorn

RUN apt-get update && apt-get install -y supervisor redis-server && apt-get install libpq-dev python3-dev -y

COPY ./supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN pip install --no-cache-dir -r requirements.txt && cd backend_django_project && python manage.py migrate

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
