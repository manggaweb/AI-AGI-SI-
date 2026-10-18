"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import re
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

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


def activity_slug(activity_name: str) -> str:
    """Build a filesystem-safe name that cannot escape the uploads directory."""
    slug = re.sub(r"[^a-z0-9]+", "-", activity_name.lower()).strip("-")
    if not slug or slug in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid activity name")
    return slug


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


def image_path_for(activity_name: str, extension: str | None = None) -> Path | None:
    slug = activity_slug(activity_name)
    if extension:
        return UPLOAD_DIR / f"{slug}{extension}"
    for ext in IMAGE_EXTENSIONS:
        candidate = UPLOAD_DIR / f"{slug}{ext}"
        if candidate.is_file():
            return candidate
    return None


def image_url_for(activity_name: str) -> str | None:
    path = image_path_for(activity_name)
    if path is None:
        return None
    return f"/uploads/{path.name}"


def delete_activity_images(activity_name: str) -> None:
    slug = activity_slug(activity_name)
    for ext in IMAGE_EXTENSIONS:
        candidate = (UPLOAD_DIR / f"{slug}{ext}").resolve()
        if UPLOAD_DIR.resolve() not in candidate.parents:
            continue
        if candidate.is_file():
            candidate.unlink()


@app.get("/activities")
def get_activities():
    result = {}
    for name, details in activities.items():
        item = dict(details)
        item["image"] = image_url_for(name)
        result[name] = item
    return result


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}


@app.post("/activities/{activity_name}/image")
async def upload_activity_image(activity_name: str, file: UploadFile = File(...)):
    """Upload or replace the image for an activity."""
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

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
    destination = image_path_for(activity_name, extension)
    resolved = destination.resolve()
    if UPLOAD_DIR.resolve() not in resolved.parents:
        raise HTTPException(status_code=400, detail="Invalid image path")

    destination.write_bytes(data)
    return {
        "message": f"Uploaded image for {activity_name}",
        "image": image_url_for(activity_name),
    }


@app.delete("/activities/{activity_name}/image")
def delete_activity_image(activity_name: str):
    """Remove the image for an activity."""
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")
    if image_url_for(activity_name) is None:
        raise HTTPException(status_code=404, detail="Activity image not found")

    delete_activity_images(activity_name)
    return {"message": f"Removed image for {activity_name}"}
