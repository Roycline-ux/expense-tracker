# 💰 Expense Tracker

A personal finance web app built with Python and Flask. Track spending, set budgets, spot trends with charts, and keep each user's data private behind a login.

The project started as a command-line script and grew step by step into a deployed multi-user web app.

## Features

- **User accounts:** registration and login with hashed passwords; each user only sees their own data
- **Expenses:** add, edit, and delete, with a custom date (future dates are rejected)
- **Search and filters:** search descriptions, filter by month and category, and combine them
- **Charts:** spending by category (doughnut) and by month (bar), powered by Chart.js
- **Budgets and alerts:** monthly limits per category or overall, with a warning at 80% and an alert when exceeded
- **Recurring expenses:** rules like "rent on day 1 of every month" that create expenses automatically, including missed months
- **CSV export:** download exactly what you are viewing, with filters applied
- **Responsive design:** works on phones, with automatic dark mode

## Tech stack

- Python 3 and Flask
- SQLite (via the built-in `sqlite3` module)
- Jinja2 templates, plain HTML and CSS
- Chart.js (loaded from a CDN)

## Project structure

```
expense-tracker/
├── app.py              # Flask app: routes, database, logic
├── tracker.py          # Original command-line version
├── templates/
│   ├── index.html      # Main dashboard
│   ├── login.html
│   ├── register.html
│   └── edit.html
├── .gitignore
└── README.md
```

## Run it locally

1. Clone the repository:
   ```bash
   git clone https://github.com/Roycline-ux/expense-tracker.git
   cd expense-tracker
   ```
2. Install Flask:
   ```bash
   pip install flask
   ```
   (On Windows you may need `py -m pip install flask`.)
3. Start the app:
   ```bash
   python app.py
   ```
   (On Windows: `py app.py`.)
4. Open http://127.0.0.1:5000, click **Create one**, and register an account.

The database file `expenses.db` is created automatically on first run.

## Configuration

Settings are read from environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs login sessions. **Set a long random value in production.** | `dev-only-change-me` |
| `ALLOW_REGISTRATION` | Set to `0` to close sign-ups | `1` |

## Deployment (PythonAnywhere)

1. Push your code to GitHub.
2. In a PythonAnywhere Bash console: `git clone https://github.com/Roycline-ux/expense-tracker.git`
3. On the **Web** tab, create a **Manual configuration** web app and set the source code to your project folder.
4. Edit the WSGI file:
   ```python
   import sys
   import os

   os.environ["SECRET_KEY"] = "a-long-random-string"
   os.environ["ALLOW_REGISTRATION"] = "1"

   path = "/home/Roycline/expense-tracker"
   if path not in sys.path:
       sys.path.insert(0, path)

   from app import app as application
   ```
5. Click **Reload**, register your account, then set `ALLOW_REGISTRATION` to `"0"` and reload again to close sign-ups.

To update the live site later: `git pull` in the Bash console, then **Reload**.

## How it works

- **Data isolation:** every query filters by `user_id`, and edit and delete also check ownership.
- **Passwords:** stored as salted hashes using Werkzeug, never in plain text.
- **SQL safety:** all values are passed as query parameters, never concatenated into SQL.
- **Recurring expenses:** generated when the dashboard is opened, using a stored "last generated month" so nothing is duplicated.
- **CSV export:** text starting with `=`, `+`, `-` or `@` is prefixed to prevent spreadsheet formula injection.

## Known limitations

- No password reset or change-password page
- No rate limiting on login attempts
- Recurring rules cannot be edited (stop one and create a new rule)
- Budget alerts appear on the page only; no email or SMS
- Recurring days are limited to 1-28
- SQLite suits personal or small-group use, not heavy concurrent traffic

## Ideas for the future

- Change-password and password-reset flow
- Editable recurring rules
- Multiple currencies
- Email budget alerts
- Import expenses from CSV

## What I learned

Git and GitHub, SQL and SQLite, Flask routing and templates, user authentication, data visualisation, and deploying a web app.

## License

Personal learning project. Add a license such as MIT if you plan to share it.