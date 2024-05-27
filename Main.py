import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from Tpas_Prepaid_Response_Time_query import Tpas_Prt_Query
import json
import splunklib.client as client
import time
import sys
import traceback


# Load variables from .env file
load_dotenv()

# Access token
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")

# Install the Slack app and get token in advance
app = App(token=slack_bot_token)

def connect_to_splunk(username, password, host='splunk-pci.t-mobile.com', port='8089', ssl_verify=False,
                      owner='kcrowe4', app='search', sharing='user'):
    try:
        service = client.connect(username=username, password=password, host=host, port=port, ssl_verify=ssl_verify,
                                 owner=owner, app=app, sharing=sharing)
        if service:
            print("Splunk service created successfully")
            print("----------------------")
    except Exception as e:
        print(e)
    return service

def saved_search_list(splunk_service):
    try:
        savedsearches = None
        savedsearches = splunk_service.saved_searches
        for s in savedsearches:
            print(s.name)
    except Exception as e:
        print(e)
    return savedsearches


def create_savedsearch(saved_search_collection, name, search, payLoad={}):
    try:
        if saved_search_collection:
            mysearch = saved_search_collection.create(name, search, **payLoad)
            if mysearch:
                print("{} object created successfully".format(mysearch.name))
                print("------------------------")
    except Exception as e:
        print(e)

@app.event("message")
def handle_message(event, say):
    channel = event["channel"]
    person = event.get("user")
    sender = event.get("bot_id")
    text = event.get("text")
    ts = event.get("ts")  # gets the thread timestamp if available
    operation = [] # Storing the operation from Splunk webhook here

    try:
        if person == os.environ["USER_ID"] and "TPAS: PREPAID API Response Time Failure" in text:
            operation = text.split("OperationName:")[1].split("|")[0].strip()
            tpas_prepaid_res_time = Tpas_Prt_Query.format(operation)

            say(text=f"I see TPAS API Failure for operation: {operation}. What would you like me to do?",
                blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"I see TPAS API Failure for operation: {operation}. What would you like me to do?"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Rerun Splunk Query",
                                "emoji": True
                            },
                            "style": "primary",
                            "action_id": "rerun_query_click"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Resolve Ticket",
                                "emoji": True
                            },
                            "style": "primary",
                            "action_id": "resolve_button_click"
                        }
                    ]
                }
            ], thread_ts=ts)
        elif person != sender:
            say(f"Hello, human", thread_ts=ts)
        else:
            say(f"Error", thread_ts=ts)
            say(f"{event}", thread_ts=ts)

    except KeyError as k:
        print(f"KeyError: {k}")
    except Exception as e:
        print(f"Exception: {e}")

# Define the callback ID for each button
rerun_query = "rerun_query_click"
resolve_button_callback_id = "resolve_button_click"
reassess_button_callback_id = "reassess_button_click"

@app.action(rerun_query)
def handle_rerun_query(ack, body, logger, say):
    # Acknowledge the button click
    ack()

    # Get information about the button click
    user_id = body["user"]["id"]
    channel_id = body["container"]["channel_id"]

    # Extract the operation from the message text
    operation = body["message"]["text"].split("TPAS API Failure for operation: ")[1].split(". What would you like me to do?")[0]

    try:
        # Create a Splunk connection
        splunk_service = connect_to_splunk(username=os.environ.get("SPLUNK_USERNAME"), password=os.environ.get("SPLUNK_PASSWORD"))
        
        # Run the Splunk search
        saved_searches = saved_search_list(splunk_service)
        name = "Tpas_PRT_Search"
        search = Tpas_Prt_Query  # assuming qvxp_search is defined in Splunk_Search_Query
        payload_search = """{
                            "dispatch.earliest_time": "-15m",
                            "dispatch.latest_time": "now"}
            """
        create_savedsearch(saved_searches, name, search, json.loads(payload_search))
        saved_search_list(splunk_service)

        mysavedsearch = splunk_service.saved_searches[name]
        job = mysavedsearch.dispatch()
        time.sleep(3)

        while True:
            job.refresh()
            stats = {"isDone": job["isDone"],
                     "doneProgress": float(job["doneProgress"]) * 100,
                     "scanCount": int(job["scanCount"]),
                     "eventCount": int(job["eventCount"]),
                     "resultCount": int(job["resultCount"])}
            status = ("\r%(doneProgress)03.1f%%   %(scanCount)d scanned   "
                      "%(eventCount)d matched   %(resultCount)d results") % stats
            sys.stdout.write(status)
            sys.stdout.flush()
            if stats["isDone"] == "1":
                print("\nJob has been created")
                break
            time.sleep(2)

        # Display search results
        jobresults = job.results(output_mode='json')
        results_json = json.loads(jobresults.read())

        for result in results_json['results']:
            print(result)
            
        # Assume you have some logic to format the Splunk results into a message
        splunk_results_message = f"Splunk Search Results\nDescription: {result['description']}\nSeverity: {result['severityOVO']}"

        # Respond in the Slack thread
        say(splunk_results_message, thread_ts=body["message"]["ts"])

    except Exception as e:
        # Handle exceptions
        traceback.print_exc()
        error_message = f"An error occurred while running the Splunk search: {str(e)}"
        say(error_message, thread_ts=body["message"]["ts"])




@app.action(resolve_button_callback_id)
def handle_resolve_button_click(ack, body, say):
    # Acknowledge the button click
    ack()

    # Perform your logic for resolving/updating resolutions
    response_message = "Severity is categorized as minor. I am closing out the ticket."

    say(response_message, thread_ts=body["message"]["ts"])

@app.action(reassess_button_callback_id)
def handle_reassess_button_click(ack, body, say):
    # Acknowledge the button click
    ack()

    # Perform your logic for reassessing after 10 minutes
    response_message = "Reassessing after 10 minutes..."

    say(response_message, thread_ts=body["message"]["ts"])

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
