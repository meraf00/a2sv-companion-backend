from flask import Flask, request, jsonify, render_template
import requests
from urllib.parse import urlparse
from urllib.parse import parse_qs
import os
from flask_cors import CORS, cross_origin
from utils import column_to_letter

from dotenv import load_dotenv
from datetime import datetime

from google.oauth2.service_account import Credentials
import gspread

import pymongo
import json
import re
from bson import json_util

import logging

# load_dotenv()


MAIN_SHEETNAME = os.getenv("MAIN_SHEET_NAME")

# gc = gspread.service_account(filename=os.getenv("GOOGLE_CREDENTIALS"))

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_info(
    json.loads(os.getenv("GOOGLE_CREDENTIALS")), scopes=scopes
)

gc = gspread.authorize(credentials)

git_client_id = os.getenv("GITHUB_CLIENT_ID")
git_client_secret = os.getenv("GITHUB_CLIENT_SECRET")

mongo_client = pymongo.MongoClient(os.getenv("MONGODB_CONNECTION_STRING"))
db = mongo_client[os.getenv("MONGODB_DB_NAME")]


app = Flask(__name__)
CORS(app)


def parse_json(data):
    return json.loads(json_util.dumps(data))


def backup(interaction, env=os.getenv("ENV")):
    # backup to google sheet b/c who knows

    # TODO: Find better way to do this
    form_url = (
        f"https://docs.google.com/forms/d/e/1FAIpQLSdPRQ-32Wl-TaA8hWvAJR1hnGjyNYfPWSRG4hiTAVfXuWc8mQ/formResponse?"
        + f"entry.422042046={interaction['Column']}"
        + f"&entry.446153335={interaction['Group']}"
        + f"&entry.1898265689={interaction['ID']}"
        + f"&entry.1842990152={interaction['Sheet']}"
        + f"&entry.127602={interaction['Number of Attempts']}"
        + f"&entry.1614409012={interaction['Person']}"
        + f"&entry.1964375111={interaction['Question_fkey']}"
        + f"&entry.976663908={interaction['Time Spent']}"
        + f"&entry.588289523={env}"
    )

    response = requests.get(form_url)

    if response.status_code != 200:
        logging.error(f"Failed to backup to google sheet: {interaction}")


def push_to_sheet(studentName, sheetName, questionColumn, gitUrl, attempts, timeTaken):
    url = (
        f"https://script.google.com/macros/s/{os.getenv('SHEET_APPSCRIPT_DEPLOYMENT')}/exec"
        + f"?studentName={studentName}&sheetName={sheetName}&questionColumn={questionColumn}&gitUrl={gitUrl}&attempts={attempts}&timeTaken={timeTaken}"
    )

    response = requests.get(url)

    if response.status_code != 200:
        logging.error(
            f"Failed to push to google sheet: {sheetName} {questionColumn} {gitUrl} {attempts}"
        )


@app.route("/api/platform", methods=["GET", "OPTIONS"])
@cross_origin()
def get_platforms():
    platforms = db.Questions.find().distinct("Platform")

    response = {"status": 200, "platforms": platforms}

    return jsonify(response)


@app.route("/api/platform/<platform>/question", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_questions(platform):
    questions = [
        parse_json(question)
        for question in db.Questions.find(
            {"Platform": re.compile(platform, re.IGNORECASE)}
        )
    ]

    response = {"status": 200, "questions": questions}

    return jsonify(response)


@app.route("/api", methods=["POST", "OPTIONS"])
@cross_origin()
def api():
    json = request.json

    attribs = [
        "studentName",
        "attempts",
        "timeTaken",
        "gitUrl",
        "questionUrl",
        "platform",
    ]

    logging.warning(f"Attemping to push: {json}")

    for atr in attribs:
        if atr not in json:
            logging.warning(f"Missing attribute: '{atr}'")
            return jsonify({"status": f"{atr} not found"}), 400

    # Push to mongodb
    student_collection = db.People
    question_collection = db.Questions

    student = student_collection.find_one({"Name": json["studentName"]})
    question = question_collection.find_one({"URL": json["questionUrl"]})

    if not student:
        logging.warning(f"Student not found on database: '{json['studentName']}'")
        return jsonify({"status": "Please check your name."}), 400

    if not question:
        logging.warning(f"Question not found on database: '{json['questionUrl']}'")
        return (
            jsonify({"status": "This question is not found on the google sheet."}),
            400,
        )

    interaction = {
        "Column": question["Column"],
        "Group": student["Group"],
        "ID": f"{student['Name']} | {question['Column']}",
        "Sheet": question["Sheet"],
        "Number of Attempts": json["attempts"],
        "Person": student["Name"],
        "Question_fkey": f"{question['Column']} | 50",
        "Time Spent": json["timeTaken"],
        "update_timestamp": datetime.now(),
    }

    db.Interactions.insert_one(interaction)

    logging.warning(f"Pushing to sheet")

    push_to_sheet(
        studentName=json["studentName"],
        sheetName=question["Sheet"],
        questionColumn=question["Column"],
        gitUrl=json["gitUrl"],
        attempts=json["attempts"],
        timeTaken=json["timeTaken"],
    )

    logging.warning(f"Successfully pushed to sheet")

    return jsonify({"status": "OK"})


@app.route("/authenticate")
def authenticate():
    github_auth_code = request.args.get("code")

    response = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": git_client_id,
            "client_secret": git_client_secret,
            "code": github_auth_code,
        },
    )

    try:
        if response.status_code == 200:
            parsed_response = urlparse(f"?{response.text}")
            access_token = parse_qs(parsed_response.query)["access_token"][0].strip()
            return render_template(
                "index.html",
                access_token=access_token,
                success=True,
                message="Successfully authenticated!",
            )
        else:
            return render_template(
                "index.html",
                access_token=access_token,
                success=False,
                message="Authentication failed!",
            )
    except:
        return render_template(
            "index.html",
            access_token=access_token,
            success=False,
            message="Authentication failed!",
        )


@app.route("/")
def home():
    return jsonify(f"Attached to sheet '{os.getenv('MAIN_SHEET_NAME')}'")


# if __name__ == "__main__":
#     app.run(debug=True)
