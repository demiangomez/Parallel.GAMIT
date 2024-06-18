# syntax=docker/dockerfile:1
# using django development server
FROM python:3
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code
COPY . /code/
RUN pip install -r requirements.txt
CMD pip install -r requirements.txt && cd backend_django_project && python manage.py migrate && python manage.py runserver 0.0.0.0:8000
EXPOSE 8000
