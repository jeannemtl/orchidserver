import os
import json
import time
import subprocess
import logging
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters
from google.cloud import texttospeech
from google.oauth2.service_account import Credentials
import boto3
import asyncio
import tempfile
import requests
from asyncio import gather
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify


# Set PyTorch environment variable
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define constants
TELEGRAM_TOKEN = "6235350336:AAEYV5ZknQJzfMOHuHa6rt0EIj6zEexO6i8"
GOOGLE_BUCKET_NAME = "victoriabucketohio2"
GOOGLE_KEY_NAME = "google.json"
MODEL_PATH_1 = "./mnt/efs/fs1/so-vits-svc-fork-main/logs/44k/uma/G_10000.pth"
CONFIG_PATH_1 = "./mnt/efs/fs1/so-vits-svc-fork-main/configs_logs/config.json"
KMEANS_PATH_1 = "./mnt/efs/fs1/so-vits-svc-fork-main/logs/44k/uma/kmeans.pt"
MODEL_PATH_2 = "./mnt/efs/fs1/so-vits-svc-frk-main/logs/44k_MAY26/G_10000.pth"
CONFIG_PATH_2 = "./mnt/efs/fs1/so-vits-svc-fork-main/configs_logs/config.json"

# Initialize Google credentials
GOOGLE_CREDENTIALS = None
executor = ThreadPoolExecutor(max_workers=2)


def get_google_credentials():
    bucket_name = "victoriabucketohio2"  # The name of your S3 bucket
    key_name = "google.json"  # The key of your service account file in S3

    # Create an S3 client
    s3 = boto3.client("s3")

    # Download the file to /tmp (a writable directory in AWS Lambda)
    download_path = "/tmp/" + key_name
    s3.download_file(bucket_name, key_name, download_path)

    # Load the service account key from the downloaded file
    with open(download_path, "r") as f:
        service_account_info = json.load(f)

    # Create Google credentials from the service account info
    credentials = Credentials.from_serovice_account_info(service_account_info)

    return credentials


def get_google_credentials_locally():
    key_file_path = "google.json"  # The path to your service account file

    # Load the service account key from the file
    with open(key_file_path, "r") as f:
        service_account_info = json.load(f)

    # Create Google credentials from the service account info
    credentials = Credentials.from_service_account_info(service_account_info)

    return credentials

    # Use asyncio to run the asynchronous handler


def lambda_handler(event, context):
    # bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
    # bot = Bot(token=os.environ["6235350336:AAEYV5ZknQJzfMOHuHa6rt0EIj6zEexO6i8"])
    bot = Bot(token="6235350336:AAEYV5ZknQJzfMOHuHa6rt0EIj6zEexO6i8")

    # update = Update.de_json(event["body"], bot)
    update = Update.de_json(json.loads(event["body"]), bot)
    send_response_to_frontend(update.message.text)
    dispatcher = Dispatcher(bot, None, workers=1)
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), echo))

    dispatcher.process_update(update)


def send_response_to_frontend(text):
    try:
        # Define the endpoint of your React Native frontend
        frontend_endpoint = "http://127.0.0.1:5000/receive_response"

        # Make a POST request to your React Native frontend with the response text
        response = requests.post(frontend_endpoint, json={"response": text})

        if response.ok:
            print("Response sent to React Native frontend successfully")
        else:
            print("Failed to send response to React Native frontend")
    except Exception as e:
        print("Error sending response to React Native frontend:", str(e))


# update.message.reply_text(update.message.text)
def echo(update, context):
    text = update.message.text

    # First, convert the text to speech and save it as a .wav file
    text_to_speech_file = generate_uma_voice(text)

    # Log the file path for debugging
    logger.info(f"Generated audio file: {text_to_speech_file}")

    # Send the voice message to Telegram
    context.bot.send_voice(
        chat_id=update.effective_chat.id, voice=open(text_to_speech_file, "rb")
    )

    # Send the text message to Telegram
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def handle_telegram_update_async(update, context):
    try:
        # Send the text to the React Native frontend

        # Echo the user's message (optional)
        update.message.reply_text(update.message.text)

        # Run the asynchronous coroutine to generate the voice
        text_to_speech_file = generate_uma_voice(update.message.text)

        # Send the voice message to Telegram
        context.bot.send_voice(
            chat_id=update.effective_chat.id,
            voice=open(text_to_speech_file, "rb"),
        )

    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))
        # Handle error (e.g., log, return an error response, etc.)


def generate_uma_voice(text):
    # Get the Google credentials
    logger.info(subprocess.check_output("which svc", shell=True))
    credentials = get_google_credentials_locally()

    # Create a unique filename for each process
    input_file = f"{os.getpid()}_input.wav"
    output_file = f"{os.getpid()}_input.out.wav"

    # Generate a .wav file from text
    text_to_speech(text, input_file, credentials)

    model_path = "./mnt/efs/fs1/so-vits-svc-fork-main/logs/44k/uma/G_10000.pth"
    config_path = "./mnt/efs/fs1/so-vits-svc-fork-main/configs_logs/config.json"
    kmeans_path = "./mnt/efs/fs1/so-vits-svc-fork-main/logs/44k/uma/kmeans.pt"

    # Use subprocess to run the 'svc infer' command with the kmeans file
    cmd = f"svc infer {input_file} -s speaker -r 0.1 -m {model_path} -c {config_path} -k {kmeans_path}"
    # cmd = f"svc infer {input_file} -s speaker -r 0.1 -m {model_path} -c {config_path}"
    try:
        result = subprocess.run(
            cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        print("stdout:", result.stdout.decode("utf-8"))
        print("stderr:", result.stderr.decode("utf-8"))

    except FileNotFoundError as e:
        logger.error("The 'svc' command was not found. Please check your Lambda layer.")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"'svc' command failed with error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        raise

    return output_file


def text_to_speech(text, output_file, credentials):
    # Instantiates a client with the provided credentials
    client = texttospeech.TextToSpeechClient(credentials=credentials)

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code ("en-GB") and the ssml
    # voice gender ("neutral")
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-GB",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        name="en-GB-Neural2-A",
    )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # The response's audio_content is binary.
    with open(output_file, "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)
    logger.info('Audio content written to file "%s"', output_file)


if __name__ == "__main__":
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
                    "text": "Many thought the latest Supreme Court decision might more clearly delineate what qualifies a work as transformative. But the justices chose instead to focus on how the Warhol portrait had been used, namely to illustrate an article about the musician. The court found that such a use was not distinct enough from the “purpose and character” of Goldsmith’s photo, which had been licensed to Vanity Fair years earlier to help illustrate an article about Prince.",
                },
            }
        )
    }

    # Call your function with the event data
    lambda_handler(event, None)
