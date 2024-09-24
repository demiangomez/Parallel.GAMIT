from celery import shared_task
import time
from . import utils

@shared_task
def update_gaps_status():
    utils.StationMetaUtils.update_gaps_status_for_all_station_meta_needed()
