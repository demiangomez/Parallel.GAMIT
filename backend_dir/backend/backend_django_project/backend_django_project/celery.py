from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_django_project.settings')
app = Celery('backend_django_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
