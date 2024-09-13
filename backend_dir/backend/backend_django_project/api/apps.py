from django.apps import AppConfig
import threading
import time
import schedule
import sys
import os

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    continuous_thread = None

    def ready(self):
        
        def run_background_job_continuously(interval=300):
            """
               This function continuously executes all pending tasks in a separate thread.
               Leaves a pause of `interval` seconds between each executing.
            """
            cease_continuous_run = threading.Event()

            class ScheduleThread(threading.Thread):
                @classmethod
                def run(cls):
                    while not cease_continuous_run.is_set():
                        time.sleep(interval)
                        schedule.run_pending()

            continuous_thread = ScheduleThread()
            continuous_thread.start()

            return continuous_thread, cease_continuous_run
        
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        if int(getattr(settings, 'MAX_SIZE_IMAGE_MB', None)) > 75:
            raise ImproperlyConfigured("MAX_SIZE_IMAGE_MB must be equal or less than 75 MB")
        
        if int(getattr(settings, 'MAX_SIZE_FILE_MB', None)) > 75:
            raise ImproperlyConfigured("MAX_SIZE_FILE_MB must be equal or less than 75 MB")
        
        # to avoid running the job when calling migrate, makemigrations, and so on. also avoid re-running the job when the server is restarted
        if (os.environ.get('GUNICORN_SERVER') == 'true' ) or ('runserver' in sys.argv and os.environ.get('RUN_MAIN') == 'true'):
            from . import utils
            from django.conf import settings

            schedule.every().second.do(utils.StationMetaUtils.update_has_gaps_status)
            
            if self.continuous_thread is None:
                self.continuous_thread, _ = run_background_job_continuously(int(settings.HAS_GAPS_BACKGROUND_JOB_TIME_INTERVAL_SECONDS))