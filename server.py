""" Copyright (c) 2021 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

__author__ = "Simon Fang <sifang@cisco.com>"
__copyright__ = "Copyright (c) 2022 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

# Import Section
from flask import Flask, request, render_template, redirect, jsonify
from dotenv import load_dotenv
import time
import os
import sys
import requests, urllib
from requests_toolbelt.multipart.encoder import MultipartEncoder
import json

# load all environment variables
load_dotenv()

########################
### Global variables ###
########################

WEBEX_BASE_URL = "https://webexapis.com/v1"
WEBEX_BOT_TOKEN = os.getenv("WEBEX_BOT_TOKEN")
WEBEX_BOT_EMAIL = os.getenv("WEBEX_BOT_EMAIL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

WEBEX_INTEGRATION_CLIENT_ID = os.getenv("WEBEX_INTEGRATION_CLIENT_ID")
WEBEX_INTEGRATION_CLIENT_SECRET = os.getenv("WEBEX_INTEGRATION_CLIENT_SECRET")
WEBEX_INTEGRATION_REDIRECT_URI = os.getenv("WEBEX_INTEGRATION_REDIRECT_URI")
WEBEX_INTEGRATION_SCOPE = os.getenv("WEBEX_INTEGRATION_SCOPE")

webex_access_token = ""
WEBEX_ROOM_ID = ""

app = Flask(__name__)

########################
### Helper Functions ###
########################

def get_webhooks():
    url = f"{WEBEX_BASE_URL}/webhooks"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {webex_access_token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    webhooks = response.json()['items']
    return webhooks

def delete_webhook(webhook_id):
    url = f"{WEBEX_BASE_URL}/webhooks/{webhook_id}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {webex_access_token}"
    }
    response_webhook = requests.delete(url, headers=headers)
    response_webhook.raise_for_status()
    return response_webhook.ok

def post_webhook():
    url = f"{WEBEX_BASE_URL}/webhooks"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {webex_access_token}"
    }

    data = {
        "name": "Webex Transcript Webhook",
        "targetUrl": WEBHOOK_URL,
        "resource": "meetingTranscripts",
        "event": "created"
    }
    response_webhook = requests.post(url, json=data, headers=headers)
    response_webhook.raise_for_status()
    return response_webhook


def register_webhook():
    # Get list of webhooks
    webhooks = get_webhooks()
    app.logger.info(json.dumps(webhooks, indent=2))

    # First, let's remove the old webhooks
    for webhook in webhooks:
        webhook_id = webhook["id"]
        if delete_webhook(webhook_id):
            app.logger.info(f"We have successfully deleted webhook with webhook id: {webhook_id}")
        else:
            app.logger.warning(f"We could not delete webhook with webhook id: {webhook_id}")
    
    response_post_webhook = post_webhook()

    if response_post_webhook.ok:
        app.logger.info("We have successfully registered a webhook")
        app.logger.info(json.dumps(response_post_webhook.json(), indent=2))
        return 1
    else:
        app.logger.warning("Webhook has not successfully registered! Please try again.")
        return 0
    

def send_transcript_to_webex(file, topic):
    try:
        app.logger.info(f"We are sending the recording with the title {topic}")
        payload = {'roomId': WEBEX_ROOM_ID}
        payload['markdown'] = f"The transcript of the recording with the title _{topic}_ is ready"
        payload['files'] = (f"transcript - {topic}.vtt", file.read(), "text/vtt")
        data = MultipartEncoder(payload)
        response = requests.post('https://api.ciscospark.com/v1/messages', data=data,
                        headers={'Authorization': f'Bearer {WEBEX_BOT_TOKEN}',
                                'Content-Type': data.content_type})
        response.raise_for_status()
        app.logger.info(f"The recording with the title {topic} has been successfully sent")
        app.logger.info(json.dumps(response.json(), indent=2))
        return 1
    except Exception as e:
        print(e)
        return 0

def get_meeting_details(meeting_id):
    # Get Meeting Details: https://developer.webex.com/docs/api/v1/meetings/get-a-meeting
    url = f"{WEBEX_BASE_URL}/meetings/{meeting_id}"
    response = requests.get(url, headers = {
        "Authorization" : f"Bearer {webex_access_token}"
    })
    response.raise_for_status()
    return response

def get_meeting_transcript(transcript_id, meeting_id):
    # Download Meeting Transcript: https://developer.webex.com/docs/api/v1/meeting-transcripts/download-a-meeting-transcript
    url = f"{WEBEX_BASE_URL}/meetingTranscripts/{transcript_id}/download?meetingId={meeting_id}"
    response = requests.get(url, headers = {
        "Authorization" : f"Bearer {webex_access_token}"
    })
    response.raise_for_status()
    return response

def get_rooms():
    # Download list of rooms: https://developer.webex.com/docs/api/v1/rooms/list-rooms
    url = f"{WEBEX_BASE_URL}/rooms?sortBy=lastactivity&type=group&max=1000"
    response = requests.get(url, headers = {
        "Authorization" : f"Bearer {webex_access_token}"
    })
    response.raise_for_status()
    rooms = response.json()['items']
    return rooms

def add_bot_to_room(room_id):
    # Download list of rooms: https://developer.webex.com/docs/api/v1/rooms/list-rooms
    url = f"{WEBEX_BASE_URL}/memberships"
    payload = {
        "roomId": room_id,
        "personEmail": WEBEX_BOT_EMAIL 
    }
    response = requests.post(url, json=payload, headers = {
        "Authorization" : f"Bearer {webex_access_token}"
    })
    print(response.json())
    return response


##############
### Routes ###
##############

# login page
@app.route('/')
def mainpage():
    return render_template('mainpage_login.html')

# webex access token
@app.route('/webexlogin', methods=['POST'])
def webexlogin():
    WEBEX_USER_AUTH_URL = WEBEX_BASE_URL + "/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&response_mode=query&scope={scope}".format(
        client_id=urllib.parse.quote(WEBEX_INTEGRATION_CLIENT_ID),
        redirect_uri=urllib.parse.quote(WEBEX_INTEGRATION_REDIRECT_URI),
        scope=urllib.parse.quote(WEBEX_INTEGRATION_SCOPE)
    )

    return redirect(WEBEX_USER_AUTH_URL)

# Main page of the app
@app.route('/webexoauth', methods=['GET'])
def webexoauth():
    global sites
    global webex_access_token

    webex_code = request.args.get('code')
    headers_token = {
        "Content-type": "application/x-www-form-urlencoded"
    }
    body = {
        'client_id': WEBEX_INTEGRATION_CLIENT_ID,
        'code': webex_code,
        'redirect_uri': WEBEX_INTEGRATION_REDIRECT_URI,
        'grant_type': 'authorization_code',
        'client_secret': WEBEX_INTEGRATION_CLIENT_SECRET
    }
    get_token = requests.post(WEBEX_BASE_URL + "/access_token?", headers=headers_token, data=body)
    app.logger.info(json.dumps(get_token.json(), indent=2))

    webex_access_token = get_token.json()['access_token']
    app.logger.info(webex_access_token)

    if register_webhook():
        app.logger.info("Webhook has been successfully registered")
    else:
        app.logger.error("No webhook is registered")
        sys.exit()

    spaces = get_rooms()
    print(spaces)
    return render_template('choose_space.html', spaces=spaces)

@app.route('/select_space', methods=['GET', 'POST'])
def select_space():
    if request.method == "POST":
        form_data = request.form
        app.logger.info(form_data)
        global WEBEX_ROOM_ID
        WEBEX_ROOM_ID = form_data['space']
        add_bot_response = add_bot_to_room(WEBEX_ROOM_ID)
        if add_bot_response.status_code == 409:
            app.logger.info("Bot has been added to room already")
    return render_template('success.html')

@app.route('/webhook_listener', methods=['GET','POST'])
def listen_for_webex_recoding_alert():
    if request.method == 'POST':
        try:
            # Get the contents of the webhook
            meeting_transcript_webhook = request.get_json()
            app.logger.info("Response of the webhook:")
            app.logger.info(json.dumps(meeting_transcript_webhook, indent=2))

            # Extract the relevant information from the webhook
            transcript_id = meeting_transcript_webhook["data"]["id"]
            meeting_id = meeting_transcript_webhook["data"]["meetingId"]
            app.logger.info(f"Transcript id is {transcript_id} and meeting id is {meeting_id}")

            # Obtain the meeting transcript
            meeting_transcript_response = get_meeting_transcript(transcript_id, meeting_id)

            # Obtain the meeting details
            meeting_response = get_meeting_details(meeting_id).json()
            meeting_name = f'{meeting_response["title"]} {meeting_response["start"]}'

            # Temporarily save the transcript file
            meeting_transcript_file = f'/tmp/{meeting_name}.vtt'
            with open(meeting_transcript_file, 'w') as file:
                file.write(meeting_transcript_response.text)

            # Send the transcript file to Webex
            app.logger.info("Let's send the transcript to webex")
            if send_transcript_to_webex(open(meeting_transcript_file, 'r'), meeting_name):
                app.logger.info("The transcript has been successfully sent to Webex")
            else:
                app.logger.warning("An error has occurred and the transcript has failed to send")
                return "", 500

            return "The transcript has been successfully delivered", 200
        except Exception as e:
            app.logger.warning(e)
            return "", 500
    else:
        return "", 200

@app.route('/remove_webhook', methods=['GET','POST'])
def remove_webhook():
    if request.method == 'POST':
        try:
            # Get list of webhooks
            webhooks = get_webhooks()
            print(json.dumps(webhooks, indent=2))

            # First, let's remove the old webhooks
            for webhook in webhooks:
                webhook_id = webhook["id"]
                if delete_webhook(webhook_id):
                    print(f"We have successfully deleted webhook with webhook id: {webhook_id}")
                else:
                    print(f"We could not delete webhook with webhook id: {webhook_id}")

            return render_template('final.html')
        except Exception as e:
            print(e)
            return render_template('final.html')
    return render_template('final.html')

if __name__ == "__main__":
    app.run(host="127.0.0.1", port="5000", debug=True) # http://127.0.0.1:5000/