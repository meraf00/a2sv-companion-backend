from flask import Flask, request, jsonify, render_template
import requests
from urllib.parse import urlparse
from urllib.parse import parse_qs
import os
from flask_cors import CORS, cross_origin
from utils import column_to_letter

from dotenv import load_dotenv

import gspread
import pymongo

load_dotenv()

MAIN_SHEETNAME = os.getenv("MAIN_SHEET_NAME")

gc = gspread.service_account(filename=os.getenv("GOOGLE_CREDENTIALS"))

git_client_id = os.getenv("GITHUB_CLIENT_ID")
git_client_secret = os.getenv("GITHUB_CLIENT_SECRET")

mongo_client = pymongo.MongoClient(os.getenv("MONGODB_CONNECTION_STRING"))
db = mongo_client[os.getenv("MONGODB_DB_NAME")]


app = Flask(__name__)
CORS(app, support_credentials=True)


def backup(interaction):
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
    )

    requests.get(form_url)


@app.route("/api", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
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
    print(json)
    for atr in attribs:
        if atr not in json:
            return "", 400

    # Push to mongodb
    student_collection = db.People
    # question_collection = db.QuestionTest
    question_collection = db.Question

    student = student_collection.find_one({"Name": json["studentName"]})
    question = question_collection.find_one({"URL": json["questionUrl"]})

    if not student or not question:
        return "", 400

    sh = gc.open(MAIN_SHEETNAME)

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

    # db.Interactions.insert_one(interaction)
    db.InteractionTest.insert_one(interaction)

    try:
        backup(interaction)
    except:
        pass

    # Attach to google sheet
    ws = sh.worksheet(question["Sheet"])

    studentNames = ws.col_values(1)

    studentRow = None
    for row, name in enumerate(studentNames):
        if name == student["Name"]:
            studentRow = row + 1
            break
    else:
        return "", 400

    questionColumn = column_to_letter(question["Column"])
    timespentColumn = column_to_letter(question["Column"] + 1)

    ws.update_acell(
        f"{questionColumn}{studentRow}",
        f'=HYPERLINK("{json["gitUrl"]}", "{json["attempts"]}")',
    )
    ws.format(f"{questionColumn}{studentRow}", {"horizontalAlignment": "RIGHT"})
    ws.update_acell(
        f"{timespentColumn}{studentRow}",
        json["timeTaken"],
    )
    ws.format(f"{timespentColumn}{studentRow}", {"horizontalAlignment": "RIGHT"})
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


if __name__ == "__main__":
    app.run(debug=True)