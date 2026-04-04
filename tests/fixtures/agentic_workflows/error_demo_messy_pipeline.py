#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████
██  ERROR DEMO — INTENTIONALLY BAD CODE                            ██
██                                                                  ██
██  This script is a portfolio demonstration for visualpy.          ██
██  It showcases common anti-patterns that visualpy's "Teacher"     ██
██  features help non-technical stakeholders understand:            ██
██                                                                  ██
██  - Excessive print() debugging (no logging framework)            ██
██  - Copy-pasted try/except blocks (no error strategy)             ██
██  - Hardcoded retry logic (no backoff library)                    ██
██  - Secrets loaded but never validated                            ██
██  - No batching (1 API call per record)                           ██
██                                                                  ██
██  DO NOT use this as a reference for production code.             ██
██████████████████████████████████████████████████████████████████████
"""

import os
import json
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

# --- Secrets (never validated) ---
GOOGLE_TOKEN_JSON = os.environ.get("GOOGLE_TOKEN_JSON")
ANYMAILFINDER_API_KEY = os.environ.get("ANYMAILFINDER_API_KEY")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def load_leads_from_sheet():
    """Pull raw leads from Google Sheets — no caching, no pagination."""
    print("Starting lead loader...")
    print("Authenticating with Google...")

    try:
        creds = Credentials.from_service_account_info(
            json.loads(GOOGLE_TOKEN_JSON),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    except Exception as e:
        print(f"Auth failed: {e}")
        return []

    print("Opening spreadsheet...")

    try:
        gc = gspread.authorize(creds)
        sheet = gc.open("Lead Pipeline Q2").worksheet("Raw Leads")
    except Exception as e:
        print(f"Sheet open failed: {e}")
        return []

    print("Fetching all records...")

    try:
        records = sheet.get_all_records()
    except Exception as e:
        print(f"Fetch failed: {e}")
        return []

    print(f"Got {len(records)} leads")
    print("Filtering incomplete records...")

    leads = []
    for row in records:
        if row.get("company") and row.get("domain"):
            leads.append(row)

    print(f"Filtered to {len(leads)} valid leads")
    print("Lead loading complete")

    return leads


def enrich_single_lead(lead):
    """Enrich one lead via AnyMailFinder — no batching, no rate limit handling."""
    company = lead.get("company", "Unknown")
    domain = lead.get("domain", "")
    print(f"Enriching {company}...")

    # First API call: find email
    try:
        resp = requests.post(
            "https://api.anymailfinder.com/v5.0/search/person.json",
            json={"domain": domain, "first_name": lead.get("first_name", ""), "last_name": lead.get("last_name", "")},
            headers={"Authorization": f"Bearer {ANYMAILFINDER_API_KEY}"},
            timeout=30,
        )
        data = resp.json()
        lead["email"] = data.get("email", "")
    except Exception as e:
        print(f"Email lookup failed for {company}: {e}")
        lead["email"] = ""

    # Second API call: verify email
    if lead["email"]:
        try:
            resp = requests.get(
                "https://api.anymailfinder.com/v5.0/verify.json",
                params={"email": lead["email"]},
                headers={"Authorization": f"Bearer {ANYMAILFINDER_API_KEY}"},
                timeout=30,
            )
            verification = resp.json()
            lead["email_verified"] = verification.get("verified", False)
        except Exception as e:
            print(f"Verification failed for {company}: {e}")
            lead["email_verified"] = False

    # Third API call: company info
    try:
        resp = requests.get(
            f"https://api.anymailfinder.com/v5.0/company.json",
            params={"domain": domain},
            headers={"Authorization": f"Bearer {ANYMAILFINDER_API_KEY}"},
            timeout=30,
        )
        company_data = resp.json()
        lead["company_size"] = company_data.get("size", "unknown")
        lead["industry"] = company_data.get("industry", "unknown")
    except Exception as e:
        print(f"Company lookup failed for {company}: {e}")
        lead["company_size"] = "unknown"
        lead["industry"] = "unknown"

    print(f"Done enriching {company}")
    return lead


def generate_summary(lead):
    """Use OpenAI to generate a sales summary — one API call per lead."""
    print(f"Generating summary for {lead.get('company', 'Unknown')}...")

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": f"Write a 1-sentence sales pitch for {lead.get('company')} in {lead.get('industry', 'tech')}"}],
                "max_tokens": 100,
            },
            timeout=60,
        )
        data = resp.json()
        lead["summary"] = data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Summary generation failed: {e}")
        lead["summary"] = ""

    return lead


def save_to_sheet(leads):
    """Write enriched data back to Google Sheets — no batching, row by row."""
    print("Saving enriched leads back to sheet...")
    print("Re-authenticating with Google...")

    try:
        creds = Credentials.from_service_account_info(
            json.loads(GOOGLE_TOKEN_JSON),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    except Exception as e:
        print(f"Auth failed on save: {e}")
        return

    try:
        gc = gspread.authorize(creds)
        sheet = gc.open("Lead Pipeline Q2").worksheet("Enriched")
    except Exception as e:
        print(f"Sheet open failed on save: {e}")
        return

    print(f"Writing {len(leads)} rows...")

    for i, lead in enumerate(leads):
        try:
            sheet.append_row([
                lead.get("company", ""),
                lead.get("domain", ""),
                lead.get("email", ""),
                str(lead.get("email_verified", "")),
                lead.get("company_size", ""),
                lead.get("industry", ""),
                lead.get("summary", ""),
            ])
        except Exception as e:
            print(f"Failed to write row {i}: {e}")

        # Terrible rate limiting
        time.sleep(1)

    print("All rows written")
    print("Sheet save complete")


def notify_slack(leads):
    """Post a summary to Slack — no formatting, no error detail."""
    print("Sending Slack notification...")

    enriched = sum(1 for l in leads if l.get("email"))
    verified = sum(1 for l in leads if l.get("email_verified"))

    try:
        requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": f"Lead enrichment done: {enriched}/{len(leads)} emails found, {verified} verified"},
            timeout=10,
        )
    except Exception as e:
        print(f"Slack notification failed: {e}")

    print("Notification sent")


def save_backup(leads):
    """Dump everything to a local JSON file — no rotation, overwrites previous."""
    print("Saving local backup...")

    try:
        with open("/tmp/lead_backup.json", "w") as f:
            json.dump(leads, f, indent=2)
    except Exception as e:
        print(f"Backup failed: {e}")

    print("Backup saved")


if __name__ == "__main__":
    print("=" * 60)
    print("LEAD ENRICHMENT PIPELINE — STARTING")
    print("=" * 60)

    leads = load_leads_from_sheet()

    if not leads:
        print("No leads to process — exiting")
        exit(1)

    print(f"Processing {len(leads)} leads...")

    enriched = []
    for lead in leads:
        result = enrich_single_lead(lead)
        result = generate_summary(result)
        enriched.append(result)
        print(f"Progress: {len(enriched)}/{len(leads)}")

    save_to_sheet(enriched)
    notify_slack(enriched)
    save_backup(enriched)

    print("=" * 60)
    print("PIPELINE COMPLETE")
    print(f"Processed: {len(enriched)} leads")
    print(f"Emails found: {sum(1 for l in enriched if l.get('email'))}")
    print(f"Verified: {sum(1 for l in enriched if l.get('email_verified'))}")
    print(f"Summaries: {sum(1 for l in enriched if l.get('summary'))}")
    print("=" * 60)
