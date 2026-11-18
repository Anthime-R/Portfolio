"""Daily GoatCounter report sent by email.

Runs in GitHub Actions (see .github/workflows/daily-stats.yml). Uses only the
Python standard library. Required environment variables (GitHub secrets):
    GOATCOUNTER_TOKEN   API key with the "Read statistics" permission
    GMAIL_ADDRESS       Gmail address used to send the report
    GMAIL_APP_PASSWORD  16-character Gmail app password
Optional:
    REPORT_TO           Recipient (defaults to GMAIL_ADDRESS)
    GOATCOUNTER_SITE    Dashboard URL (defaults to https://anthime.goatcounter.com)
"""
import json
import os
import smtplib
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

SITE = os.environ.get("GOATCOUNTER_SITE", "https://anthime.goatcounter.com").rstrip("/")

# GitHub pauses scheduled workflows after 60 days without a commit on public repos
PAUSE_AFTER_DAYS = 60
WARN_FROM_DAY = 55


def days_since_last_commit():
    """Days since the latest commit of the repository, or None if git is unavailable."""
    try:
        ts = subprocess.run(["git", "log", "-1", "--format=%ct"], capture_output=True, text=True, check=True).stdout.strip()
        return (datetime.now(timezone.utc) - datetime.fromtimestamp(int(ts), timezone.utc)).days
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def api(path, **params):
    """GET a GoatCounter API endpoint and return the decoded JSON."""
    url = f"{SITE}/api/v0/{path}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["GOATCOUNTER_TOKEN"],
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def collect(start, end):
    """Fetch yesterday's numbers: totals, pages, link clicks, referrers, countries, devices."""
    rng = {"start": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": end.strftime("%Y-%m-%dT%H:%M:%SZ")}
    total = api("stats/total", **rng)
    hits = api("stats/hits", limit=50, **rng).get("hits", [])
    stat = lambda page: api(f"stats/{page}", limit=8, **rng).get("stats", [])
    return {
        "visitors": total.get("total", 0) - total.get("total_events", 0),
        "clicks_total": total.get("total_events", 0),
        "pages": [(h["path"], h["count"]) for h in hits if not h.get("event")],
        "clicks": [(h["path"], h["count"]) for h in hits if h.get("event")],
        "referrers": [(s["name"] or "(direct)", s["count"]) for s in stat("toprefs")],
        "countries": [(s["name"], s["count"]) for s in stat("locations")],
        "systems": [(s["name"], s["count"]) for s in stat("systems")],
    }


def render(day, d):
    """Build the plain-text report."""
    def block(title, rows, empty="—"):
        lines = [f"\n\n{title}"]
        lines += [f"  {count:>4}  {name}" for name, count in rows] or [f"  {empty}"]
        return "\n".join(lines)

    text = f"Portfolio · {day:%A %d %B %Y}\n"
    text += f"\nVisitors : {d['visitors']}\nLink clicks : {d['clicks_total']}\n"
    text += block("Pages", d["pages"])
    text += block("Clicks", d["clicks"])
    text += block("Came from", d["referrers"])
    text += block("Countries", d["countries"])
    text += block("Systems", d["systems"])
    text += f"\n\nDashboard: {SITE}\n"
    return text


def send(subject, body):
    sender = os.environ["GMAIL_ADDRESS"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = os.environ.get("REPORT_TO") or sender
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)


def main():
    # Yesterday, as a full UTC day (GoatCounter's breakdowns are stored in UTC)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=1)
    end = today - timedelta(seconds=1)
    data = collect(start, end)
    body = render(start, data)
    subject = f"Portfolio · {data['visitors']} visitor(s), {data['clicks_total']} click(s) · {start:%d/%m}"

    idle = days_since_last_commit()
    if idle is not None and idle >= WARN_FROM_DAY:
        left = max(PAUSE_AFTER_DAYS - idle, 0)
        subject = f"⚠ Commit needed ({left} day(s) left) · " + subject
        body = (f"⚠ No commit for {idle} days: GitHub pauses this daily report after {PAUSE_AFTER_DAYS} days.\n"
                f"Push any small commit to the repository to keep it running "
                f"(or re-enable the workflow in the Actions tab if it already stopped).\n\n") + body

    print(subject)
    print(body)
    if "--dry-run" in sys.argv:
        return
    send(subject, body)


if __name__ == "__main__":
    main()
