"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import hmac
import json
import os
import re
import secrets
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Activity images are stored on disk and served as static files.
UPLOAD_DIR = current_dir / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_EXTENSIONS = (".jpg", ".png", ".gif", ".webp")
ACTIVITIES_PATH = current_dir / "activities.json"
TEACHERS_PATH = current_dir / "teachers.json"
REQUIRED_ACTIVITY_FIELDS = (
    "description",
    "schedule",
    "max_participants",
    "participants",
    "category",
    "start_minutes",
)

# token -> username. Sessions reset when the server restarts.
sessions: dict[str, str] = {}


def load_activities() -> dict:
    """Load the activity list teachers can edit without touching Python."""
    with ACTIVITIES_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not data:
        raise RuntimeError("activities.json must be a non-empty object")
    for name, details in data.items():
        if not isinstance(details, dict):
            raise RuntimeError(f"{name} must be an object")
        missing = [field for field in REQUIRED_ACTIVITY_FIELDS if field not in details]
        if missing:
            raise RuntimeError(f"{name} is missing {', '.join(missing)}")
        if not isinstance(details["participants"], list):
            raise RuntimeError(f"{name} participants must be a list")
    return data


def load_teachers() -> dict[str, str]:
    """Load assigned teacher usernames and passwords."""
    with TEACHERS_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list) or not data:
        raise RuntimeError("teachers.json must be a non-empty list")
    teachers = {}
    for entry in data:
        username = str(entry.get("username", "")).strip()
        password = str(entry.get("password", ""))
        if not username or not password:
            raise RuntimeError("Each teacher needs a username and password")
        teachers[username] = password
    return teachers


activities = load_activities()
teachers = load_teachers()


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


def activity_slug(activity_name: str) -> str:
    """Build a filesystem-safe name that cannot escape the uploads directory."""
    slug = re.sub(r"[^a-z0-9]+", "-", activity_name.lower()).strip("-")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug or ""):
        raise HTTPException(status_code=400, detail="Invalid activity name")
    return slug


def resolved_upload_path(activity_name: str, extension: str) -> str:
    """Return a normalized path that is confirmed to stay inside the uploads directory."""
    if extension not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid image type")

    filename = f"{activity_slug(activity_name)}{extension}"
    root = os.path.realpath(UPLOAD_DIR)
    candidate = os.path.realpath(os.path.join(root, filename))
    if not candidate.startswith(root + os.sep):
        raise HTTPException(status_code=400, detail="Invalid image path")
    return candidate


def detect_image_extension(data: bytes) -> str | None:
    """Return an extension only when the bytes match a known image signature."""
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None


def image_url_for(activity_name: str) -> str | None:
    for extension in IMAGE_EXTENSIONS:
        path = resolved_upload_path(activity_name, extension)
        if os.path.isfile(path):
            return f"/uploads/{activity_slug(activity_name)}{extension}"
    return None


def delete_activity_images(activity_name: str) -> None:
    for extension in IMAGE_EXTENSIONS:
        path = resolved_upload_path(activity_name, extension)
        if os.path.isfile(path):
            os.remove(path)


def require_teacher(authorization: str | None = Header(default=None)) -> str:
    """Only a logged-in teacher may change registrations or images."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Teacher login required")
    token = authorization.split(" ", 1)[1].strip()
    username = sessions.get(token)
    if not username:
        raise HTTPException(status_code=401, detail="Teacher login required")
    return username


def get_activity(activity_name: str) -> dict:
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activities[activity_name]


@app.get("/activities")
def get_activities():
    result = {}
    for name, details in activities.items():
        item = dict(details)
        item["image"] = image_url_for(name)
        result[name] = item
    return result


@app.post("/login")
def login(body: LoginRequest):
    """Check an assigned teacher username and password."""
    username = body.username.strip()
    expected = teachers.get(username)
    if expected is None or not hmac.compare_digest(expected, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    for token, name in list(sessions.items()):
        if name == username:
            del sessions[token]
    token = secrets.token_urlsafe(32)
    sessions[token] = username
    return {"token": token, "username": username}


@app.post("/logout")
def logout(teacher: str = Depends(require_teacher), authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        sessions.pop(authorization.split(" ", 1)[1].strip(), None)
    return {"message": f"Logged out {teacher}"}


@app.get("/me")
def current_teacher(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        return {"logged_in": False, "username": None}
    username = sessions.get(authorization.split(" ", 1)[1].strip())
    if not username:
        return {"logged_in": False, "username": None}
    return {"logged_in": True, "username": username}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, teacher: str = Depends(require_teacher)):
    """Sign up a student for an activity. Teachers only."""
    activity = get_activity(activity_name)
    email = email.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid student email is required")

    if email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is already signed up")

    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, teacher: str = Depends(require_teacher)):
    """Unregister a student from an activity. Teachers only."""
    activity = get_activity(activity_name)

    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}


@app.post("/activities/{activity_name}/image")
async def upload_activity_image(
    activity_name: str,
    file: UploadFile = File(...),
    teacher: str = Depends(require_teacher),
):
    """Upload or replace the image for an activity. Teachers only."""
    get_activity(activity_name)

    data = await file.read(MAX_IMAGE_BYTES + 1)
    await file.close()

    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 2 MB or smaller")

    extension = detect_image_extension(data)
    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG, GIF, and WebP images are allowed",
        )

    delete_activity_images(activity_name)
    destination = resolved_upload_path(activity_name, extension)
    with open(destination, "wb") as image_file:
        image_file.write(data)
    return {
        "message": f"Uploaded image for {activity_name}",
        "image": image_url_for(activity_name),
    }


@app.delete("/activities/{activity_name}/image")
def delete_activity_image(activity_name: str, teacher: str = Depends(require_teacher)):
    """Remove the image for an activity. Teachers only."""
    get_activity(activity_name)
    if image_url_for(activity_name) is None:
        raise HTTPException(status_code=404, detail="Activity image not found")

    delete_activity_images(activity_name)
    return {"message": f"Removed image for {activity_name}"}
