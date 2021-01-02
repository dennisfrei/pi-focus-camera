import os
import logging
import json
from flask import Flask, request, jsonify, Response
from flask_restplus import Api, Resource, fields
import picamera
from dotenv import load_dotenv
from threading import Condition

# Load functions
from authorize import auth
from camera_utils import StreamingOutput
from utils import string_to_bool, setup_logger

load_dotenv()

# Enable logging
logger = setup_logger('api', 'INFO')

# Define Constants
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
DEBUG = string_to_bool(os.getenv("DEBUG", 'True'))


def gen(video_capture):
    while True:
        _, frame = video_capture.read()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


def gen_pi(output):
    while True:
        with output.condition:
            output.condition.wait()
            frame = output.frame
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


# Define Endpoint
app = Flask(__name__)
"""authorizations = {
    'apikey': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-API-KEY'
    }
}"""

api = Api(
    doc='/doc',
    app=app,
#    authorizations=authorizations,
    version="1.0.0",
    title="PI-Obs API",
    description="Handle the web streaming, option setting and capturing via API"
)

# API
application = api.namespace('api', description='PI-Obs API')

@application.route("/video-feed")
class Handler(Resource):
    @api.doc(
        responses={
            200: 'OK',
            401: 'Unauthorized: API key required',
            500: 'Internal Error'
        },
        security='apikey'
    )
    #@auth(application)
    def get(self):
        try:
            return Response(
                gen(video_capture),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

        except Exception as e:
            application.abort(
                400, e.__doc__, status="Invalid Argument", statusCode="400")


# Healthcheck
health = api.namespace(
    'healthcheck',
    description='Check if the application is still alive'
)


@health.route("/")
class HealthCheck(Resource):
    @api.doc(
        responses={
            200: 'OK',
            500: 'Internal Error'
        }
    )
    def get(self):
        try:
            return {
                "status": 1
            }, 200
        except Exception as e:
            application.abort(
                500, e.__doc__, status="Internal Error", statusCode="500")


if __name__ == "__main__":
    with picamera.PiCamera(resolution='640x480', framerate=24) as camera:
        output = StreamingOutput()
        camera.start_recording(output, format='mjpeg')
        try:
            app.run(host=HOST, port=PORT, debug=DEBUG)
        finally:
            camera.stop_recording()