# syntax=docker/dockerfile:1
# using django development server
FROM python:3.11
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code
COPY . /code/
RUN mkdir -p /var/log/gunicorn && chmod 755 /var/log/gunicorn
CMD ["sh", "-c", "pip install --no-cache-dir -r requirements.txt && cd backend_django_project && python manage.py migrate && gunicorn --bind 0.0.0.0:8000 backend_django_project.wsgi:application --env GUNICORN_SERVER=true --access-logfile - --error-logfile - --log-level info --capture-output"]
EXPOSE 8000
