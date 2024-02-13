from flask import Flask, request, jsonify
import json
import openai
import os
from flask_cors import CORS
import requests

from lambda_function import lambda_handler

# from flask_socketio import SocketIO

app = Flask(__name__)
CORS(app)
# socketio = SocketIO(app)

# Initialize OpenAI
openai_api_key = os.environ["OPENAI_API_KEY"]
openai.api_key = openai_api_key  # Set the OpenAI API key


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json()
        app.logger.info("Received request data: %s", data)  # Log the request data
        if "message" in data:
            message_text = data["message"]["text"]
            app.logger.info("Received message: %s", message_text)  # Log the message
            # Send the received message to your /send_prompt route
            response = requests.post(
                "http://localhost:5000/send_prompt",
                json={"text": message_text},
            )
            app.logger.info(
                "Response from backend: %s", response.text
            )  # Log the response
            # Handle the response from your backend if needed
        return "OK", 200
    except Exception as e:
        app.logger.error("An error occurred: %s", str(e))  # Log any exceptions
        return "Error", 500


@app.route("/receive_response", methods=["POST"])
def receive_response():
    try:
        data = request.get_json()
        response_text = data.get("response")

        # Do something with the response text, such as displaying it
        print("Received response:", response_text)

        # Send the response to the web app
        send_response_to_webapp(response_text)

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def send_response_to_webapp(response_text):
    # Define the endpoint of the web app
    webapp_endpoint = "http://localhost:5000/send_response_to_frontend"

    try:
        # Make a POST request to the web app with the response text
        response = requests.post(webapp_endpoint, json={"response": response_text})
        if response.ok:
            print("Response sent to web app successfully")
        else:
            print("Failed to send response to web app")
    except Exception as e:
        print("Error sending response to web app:", str(e))
        # You might want to handle this error case more gracefully


@app.route("/send_response_to_frontend", methods=["POST"])
def send_response_to_frontend():
    try:
        data = request.get_json()
        response_text = data.get("response")

        # Do something with the response text, such as displaying it
        print("Received response:", response_text)

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        # You might want to handle this error case more gracefully


@app.route("/send_prompt", methods=["POST"])
def receive_prompt():
    try:
        data = request.get_json()
        prompt_text = data["text"]

        # Query OpenAI's API using chat completion
        openai_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt_text}]
        )
        print("OpenAI Response:", openai_response)
        print(openai.__version__)

        generated_text = openai_response["choices"][0]["message"]["content"].strip()

        # Create the event using generated_text and pass it to lambda_handler
        event = {
            "body": json.dumps(
                {
                    "update_id": 844620471,
                    "message": {
                        "message_id": 12,
                        "from": {
                            "id": 1594434619,
                            "is_bot": False,
                            "first_name": "Jeanne",
                            "username": "prompterminal",
                            "language_code": "en",
                        },
                        "chat": {
                            "id": 1594434619,
                            "first_name": "Jeanne",
                            "username": "prompterminal",
                            "type": "private",
                        },
                        "date": 1684653648,
                        "text": generated_text,
                    },
                }
            )
        }

        lambda_handler(event, None)

        # Send a response back to the client
        response_data = {
            "message": "Prompt received and processed successfully",
            "response": generated_text,
        }
        return jsonify(response_data), 200

    except KeyError:
        return jsonify({"error": "The 'text' key is missing in the request data"}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 400


if __name__ == "__main__":
    app.run()
