from flask import Flask, request
import requests
from urllib.parse import urlparse
from urllib.parse import parse_qs
import os

import gspread
import pymongo

gc = gspread.service_account(filename=os.getenv("GOOGLE_CREDENTIALS"))

git_client_id = os.getenv("GITHUB_CLIENT_ID")
git_client_secret = os.getenv("GITHUB_CLIENT_SECRET")

mongo_client = pymongo.MongoClient(os.getenv("MONGODB_CONNECTION_STRING"))
db = mongo_client.G5_MongoDB_Charts


app = Flask(__name__)


@app.route("/api", methods=["POST"])
def api():
    json = request.json()

    attribs = [
        "studentName",
        "attempts",
        "timeTaken",
        "gitUrl",
        "questionUrl",
        "platform",
    ]

    for atr in attribs:
        if atr not in json:
            return "", 400

    # Push to mongodb
    student_collection = db.People
    question_collection = db.Question

    student = student_collection.find_one({"Name": json["studentName"]})
    question = question_collection.find_one({"URL": json["questionUrl"]})

    sh = gc.open("Copy of A2SV - G5 Main Sheet")

    interaction = {
        "Column": question["Column"],
        "Group": student["Group"],
        "ID": f"{student['Name']} | {question['Column']}",
        "Sheet": question["Sheet"],
        "Number of Attempts": json["attempts"],
        "Person": student["Name"],
        "Question_fkey": question["ID"],
        "Time Spent": json["timeTaken"],
    }

    print(interaction)
    # db.Interactions.insert_one(interaction)
    db.InteractionTest.insert_one(interaction)

    ws = sh.worksheet()

    return "OK", 200


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
            return f"<input type='hidden' value='{access_token}' id='access_token'> {access_token}"
        else:
            return ""
    except:
        return ""
