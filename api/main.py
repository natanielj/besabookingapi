import os
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from mangum import Mangum


def load_firebase_credentials():
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
    service_account_type = os.getenv("FIREBASE_TYPE")

    if private_key and service_account_type:
        service_account_info = {
            "type": service_account_type,
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": private_key.replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
            "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
            "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN"),
        }
        return credentials.Certificate(service_account_info)

    return credentials.Certificate("./serviceAccountKey.json")


firebase_cred = load_firebase_credentials()
firebase_admin.initialize_app(firebase_cred)



app = FastAPI()

FRONTEND = "https://besa-booking-git-backendv5-be-student-ambassadors-projects.vercel.app"

origins = [
    FRONTEND,
    "http://localhost:5173",
    "https://besa-booking.vercel.app",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],          # Must include OPTIONS
    allow_headers=["*"],
    allow_credentials=True,
)


DEFAULT_SCOPES = ['https://www.googleapis.com/auth/calendar']


def resolve_calendar_scopes():
    scopes_env = os.getenv("CALENDAR_SCOPES")
    if scopes_env:
        return [scope.strip() for scope in scopes_env.split(",") if scope.strip()]
    return DEFAULT_SCOPES


def load_google_calendar_credentials(scopes):
    token = os.getenv("CALENDAR_TOKEN")
    refresh_token = os.getenv("CALENDAR_REFRESH_TOKEN")
    token_uri = os.getenv("CALENDAR_TOKEN_URI")
    client_id = os.getenv("CALENDAR_CLIENT_ID")
    client_secret = os.getenv("CALENDAR_CLIENT_SECRET")

    if token and refresh_token and token_uri and client_id and client_secret:
        token_info = {
            "token": token,
            "refresh_token": refresh_token,
            "token_uri": token_uri,
            "client_id": client_id,
            "client_secret": client_secret,
            "scopes": scopes,
            "universe_domain": os.getenv("CALENDAR_UNIVERSE_DOMAIN"),
            "account": os.getenv("CALENDAR_ACCOUNT", ""),
        }
        expiry = os.getenv("CALENDAR_EXPIRY")
        if expiry:
            token_info["expiry"] = expiry

        return Credentials.from_authorized_user_info(token_info, scopes)

    return Credentials.from_authorized_user_file("token.json", scopes)


SCOPES = resolve_calendar_scopes()
creds = load_google_calendar_credentials(SCOPES)
calendar_service = build("calendar", "v3", credentials=creds)

db = firestore.client()

handler = Mangum(app)




def createEvent(data):
    start_dt = datetime.strptime(
        f"{data['date']} {data['time']}", "%Y-%m-%d %I:%M %p"
    )
    end_dt = start_dt + timedelta(hours=1)

    event = {
        "summary": data.get("tourType", "Event"),
        "description": (
            f"Tour ID: {data['tourId']}\n"
            f"Name: {data['firstName']} {data['lastName']}\n"
            f"Organization: {data['organization']}\n"
            f"Role: {data['role']}\n"
            f"Interests: {', '.join(data.get('interests', []))}\n"
            f"Notes: {data.get('notes', '')}"
        ),
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "America/Los_Angeles",
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "America/Los_Angeles",
        },
        "attendees": [
            {"email": data["email"]}
        ],
    }

    created_event = calendar_service.events().insert(
        calendarId="primary",
        body=event,
        sendUpdates="all"
    ).execute()

    return created_event




@app.get("/")
def root():
    return {"Hello": "World"}


@app.options("/book-tour/")
async def book_tour_options():
    return JSONResponse(
        content={"message": "preflight ok"},
        headers={
            "Access-Control-Allow-Origin": FRONTEND,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@app.post("/book-tour/")
async def book_tour(request: Request):
    data = await request.json()
    createEvent(data)
    return {"message": "Tour created successfully", "data": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
