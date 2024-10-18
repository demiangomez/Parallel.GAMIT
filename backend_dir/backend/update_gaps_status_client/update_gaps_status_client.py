import logging
from time import sleep
import requests


if __name__ == "__main__":
    """
    The following script is used to update the status of the gaps in the database.
    """
    timeout_value = 2 * 60 * 60 # 2 hours
    update_url = 'http://localhost:8000/api/update-gaps-status'
    delete_block_url = 'http://localhost:8000/api/delete-update-gaps-status-block'

    def get_token():
        url = 'http://localhost:8000/api/token'
        credentials = {
            'username': 'update-gaps-status',
            'password': '!pwyCZC=E#m*7Y,'
        }
        response = requests.post(url, data=credentials)

        json_response = response.json()

        if 'access' in json_response:
            return json_response['access']
        else:
            return None
        
    sleep(120) # wait for the server to start
    failed_request_counter = 0
    while True:
        
        token = get_token()
        headers = {
            'Authorization': f'Bearer {token}'
        }

        if failed_request_counter >= 20:
            requests.post(delete_block_url, headers=headers, timeout=timeout_value)

        response = requests.post(update_url, headers=headers, timeout=timeout_value)
        
        if response.status_code == 429:
            failed_request_counter += 1
        else:
            failed_request_counter = 0

        sleep(10)