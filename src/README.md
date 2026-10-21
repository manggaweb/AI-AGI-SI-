# Mergington High School Activities API

A super simple FastAPI application that allows students to view extracurricular activities and teachers to sign students up.

## Features

- View all available extracurricular activities
- Search, filter by category, and sort by name or time
- Teacher login required to register or unregister students
- Upload, replace, or remove an image for an activity (teachers only)

## Getting Started

1. Install the dependencies from the repository root:

   ```
   pip install -r requirements.txt
   ```

2. Run the application:

   ```
   uvicorn src.app:app --reload
   ```

3. Open your browser and go to:
   - App: http://localhost:8000/
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

The assigned teacher account is in `teachers.json`:

- Username: `teacher`
- Password: `schoolpride`

Add more teachers by editing that file. There is no account maintenance page.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/login`                                                          | Teacher login. JSON body with username and password                 |
| POST   | `/logout`                                                         | End the current teacher session                                     |
| GET    | `/me`                                                             | Whether the current session is a logged-in teacher                  |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Sign up for an activity (teacher only)                              |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher only)                              |
| POST   | `/activities/{activity_name}/image`                               | Upload or replace an activity image (JPEG, PNG, GIF, or WebP, 2 MB max) |
| DELETE | `/activities/{activity_name}/image`                               | Remove an activity image                                            |

Teacher-only endpoints expect an Authorization header carrying the bearer token returned by `/login`.

## Data Model

Activities live in `activities.json`, not in the Python file. Each activity uses its name as the identifier and includes:

- Description
- Schedule, kept as text, plus `start_minutes` (minutes from Monday 00:00) for sorting
- Category, used by the filter toolbar
- Maximum number of participants allowed
- List of student emails who are signed up
- Optional image stored in `uploads/` and served at `/uploads/{slug}.ext`

Students are identified by email. Sign-ups are kept in memory and reset when the server restarts. Restarting also reloads `activities.json` and `teachers.json`.
