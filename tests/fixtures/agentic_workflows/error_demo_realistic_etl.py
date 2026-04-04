#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████
██  ERROR DEMO — REALISTIC BUT PATTERN-HEAVY CODE                  ██
██                                                                  ██
██  This script is a portfolio demonstration for visualpy.          ██
██  Unlike the "messy" demo, this represents REAL production code   ██
██  that a competent developer might write. The repetitive          ██
██  patterns here are natural, not negligent:                       ██
██                                                                  ██
██  - Logging at each stage (proper observability practice)         ██
██  - Per-service error handling (isolation pattern)                ██
██  - Multiple transforms (real ETL pipeline)                       ██
██  - Validation at boundaries (defensive programming)              ██
██                                                                  ██
██  visualpy's "Teacher" features help stakeholders understand      ██
██  WHY these patterns exist — not just THAT they exist.            ██
██████████████████████████████████████████████████████████████████████
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger("invoice_sync")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# --- Configuration ---
GOOGLE_TOKEN_JSON = os.environ.get("GOOGLE_TOKEN_JSON")
PANDADOC_API_KEY = os.environ.get("PANDADOC_API_KEY")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")


class InvoiceSyncPipeline:
    """Sync invoices between PandaDoc, Stripe, and Google Sheets.

    Production ETL that runs on a daily cron schedule.
    Reads pending invoices → matches Stripe payments → updates statuses →
    notifies finance team via Slack.
    """

    def __init__(self):
        self.stats = {"fetched": 0, "matched": 0, "updated": 0, "errors": 0}
        self.errors = []

    def run(self):
        """Main orchestration — each phase isolated so one failure doesn't block others."""
        logger.info("Invoice sync pipeline starting")
        logger.info(f"Run date: {datetime.now().isoformat()}")

        # Phase 1: Gather data from all sources
        invoices = self._fetch_pandadoc_invoices()
        payments = self._fetch_stripe_payments()
        sheet_data = self._fetch_sheet_status()

        if not invoices:
            logger.warning("No invoices to process — aborting")
            self._notify_slack("Invoice sync skipped: no pending invoices found")
            return

        # Phase 2: Transform and match
        matched = self._match_invoices_to_payments(invoices, payments)
        validated = self._validate_matches(matched, sheet_data)
        enriched = self._enrich_with_metadata(validated)

        # Phase 3: Write back results
        self._update_pandadoc_statuses(enriched)
        self._update_google_sheet(enriched)
        self._archive_processed(enriched)

        # Phase 4: Report
        self._notify_slack_summary()
        self._log_final_stats()

    # --- Phase 1: Data Gathering ---

    def _fetch_pandadoc_invoices(self):
        """Fetch pending invoices from PandaDoc API."""
        logger.info("Fetching invoices from PandaDoc...")

        try:
            resp = requests.get(
                "https://api.pandadoc.com/public/v1/documents",
                params={"status": 11, "count": 100},  # status 11 = sent/pending
                headers={"Authorization": f"API-Key {PANDADOC_API_KEY}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            logger.error("PandaDoc API timed out after 30s")
            self.errors.append("PandaDoc timeout")
            return []
        except requests.HTTPError as e:
            logger.error(f"PandaDoc API returned {e.response.status_code}")
            self.errors.append(f"PandaDoc HTTP {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"PandaDoc fetch failed: {e}")
            self.errors.append(f"PandaDoc error: {e}")
            return []

        invoices = data.get("results", [])
        self.stats["fetched"] = len(invoices)
        logger.info(f"Fetched {len(invoices)} pending invoices from PandaDoc")
        return invoices

    def _fetch_stripe_payments(self):
        """Fetch recent payments from Stripe for matching."""
        logger.info("Fetching payments from Stripe...")

        cutoff = int((datetime.now() - timedelta(days=30)).timestamp())

        try:
            resp = requests.get(
                "https://api.stripe.com/v1/charges",
                params={"created[gte]": cutoff, "limit": 100},
                auth=(STRIPE_API_KEY, ""),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            logger.error("Stripe API timed out after 30s")
            self.errors.append("Stripe timeout")
            return []
        except requests.HTTPError as e:
            logger.error(f"Stripe API returned {e.response.status_code}")
            self.errors.append(f"Stripe HTTP {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Stripe fetch failed: {e}")
            self.errors.append(f"Stripe error: {e}")
            return []

        payments = data.get("data", [])
        logger.info(f"Fetched {len(payments)} payments from Stripe (last 30 days)")
        return payments

    def _fetch_sheet_status(self):
        """Fetch current invoice statuses from tracking spreadsheet."""
        logger.info("Fetching current status from Google Sheets...")

        try:
            creds = Credentials.from_service_account_info(
                json.loads(GOOGLE_TOKEN_JSON),
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
            gc = gspread.authorize(creds)
            sheet = gc.open("Invoice Tracker 2026").worksheet("Status")
            records = sheet.get_all_records()
        except Exception as e:
            logger.error(f"Google Sheets fetch failed: {e}")
            self.errors.append(f"Sheets error: {e}")
            return []

        logger.info(f"Fetched {len(records)} rows from tracking sheet")
        return records

    # --- Phase 2: Transform & Match ---

    def _match_invoices_to_payments(self, invoices, payments):
        """Match PandaDoc invoices to Stripe payments by amount and date."""
        logger.info(f"Matching {len(invoices)} invoices against {len(payments)} payments...")

        payment_index = {}
        for p in payments:
            amount = p.get("amount", 0) / 100  # Stripe amounts in cents
            payment_index.setdefault(str(amount), []).append(p)

        matched = []
        for inv in invoices:
            inv_amount = str(inv.get("grand_total", {}).get("amount", "0"))
            inv_name = inv.get("name", "")
            inv_id = inv.get("id", "")

            candidates = payment_index.get(inv_amount, [])

            if candidates:
                best = candidates[0]
                matched.append({
                    "invoice_id": inv_id,
                    "invoice_name": inv_name,
                    "amount": float(inv_amount),
                    "payment_id": best.get("id"),
                    "payment_status": best.get("status"),
                    "match_confidence": "high" if len(candidates) == 1 else "low",
                    "matched": True,
                })
                self.stats["matched"] += 1
            else:
                matched.append({
                    "invoice_id": inv_id,
                    "invoice_name": inv_name,
                    "amount": float(inv_amount),
                    "payment_id": None,
                    "payment_status": None,
                    "match_confidence": "none",
                    "matched": False,
                })

        logger.info(f"Matched {self.stats['matched']}/{len(invoices)} invoices to payments")
        return matched

    def _validate_matches(self, matched, sheet_data):
        """Cross-reference matches against sheet to catch duplicates."""
        logger.info("Validating matches against tracking sheet...")

        already_processed = {r.get("invoice_id") for r in sheet_data if r.get("status") == "paid"}

        validated = []
        skipped = 0
        for m in matched:
            if m["invoice_id"] in already_processed:
                skipped += 1
                continue
            if m["matched"] and m["match_confidence"] == "low":
                m["needs_review"] = True
            else:
                m["needs_review"] = False
            validated.append(m)

        logger.info(f"Validated {len(validated)} invoices ({skipped} already processed, skipped)")
        return validated

    def _enrich_with_metadata(self, validated):
        """Add computed fields for reporting."""
        logger.info("Enriching with metadata...")

        for item in validated:
            # Clean invoice name
            name = item.get("invoice_name", "")
            item["client_name"] = re.sub(r"^INV-\d+-", "", name).strip() or name

            # Determine action needed
            if item["matched"] and not item.get("needs_review"):
                item["action"] = "auto_mark_paid"
            elif item["matched"] and item.get("needs_review"):
                item["action"] = "manual_review"
            else:
                item["action"] = "follow_up"

            # Add timestamp
            item["processed_at"] = datetime.now().isoformat()

        auto = sum(1 for v in validated if v["action"] == "auto_mark_paid")
        review = sum(1 for v in validated if v["action"] == "manual_review")
        follow_up = sum(1 for v in validated if v["action"] == "follow_up")
        logger.info(f"Actions: {auto} auto-pay, {review} review, {follow_up} follow-up")

        return validated

    # --- Phase 3: Write Back ---

    def _update_pandadoc_statuses(self, enriched):
        """Update invoice statuses in PandaDoc for auto-matched items."""
        logger.info("Updating PandaDoc statuses...")

        auto_pay = [e for e in enriched if e["action"] == "auto_mark_paid"]

        for item in auto_pay:
            try:
                resp = requests.patch(
                    f"https://api.pandadoc.com/public/v1/documents/{item['invoice_id']}/status",
                    json={"status": 12},  # 12 = completed
                    headers={"Authorization": f"API-Key {PANDADOC_API_KEY}"},
                    timeout=15,
                )
                resp.raise_for_status()
                self.stats["updated"] += 1
            except Exception as e:
                logger.error(f"Failed to update PandaDoc status for {item['invoice_id']}: {e}")
                self.stats["errors"] += 1

        logger.info(f"Updated {self.stats['updated']}/{len(auto_pay)} invoice statuses in PandaDoc")

    def _update_google_sheet(self, enriched):
        """Append processing results to tracking spreadsheet."""
        logger.info("Updating Google Sheets tracking...")

        try:
            creds = Credentials.from_service_account_info(
                json.loads(GOOGLE_TOKEN_JSON),
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            gc = gspread.authorize(creds)
            sheet = gc.open("Invoice Tracker 2026").worksheet("Status")
        except Exception as e:
            logger.error(f"Failed to open sheet for writing: {e}")
            self.errors.append(f"Sheet write auth error: {e}")
            return

        rows = []
        for item in enriched:
            rows.append([
                item["invoice_id"],
                item["client_name"],
                str(item["amount"]),
                item["action"],
                item["match_confidence"],
                item["processed_at"],
            ])

        try:
            if rows:
                sheet.append_rows(rows)
        except Exception as e:
            logger.error(f"Failed to write {len(rows)} rows to sheet: {e}")
            self.errors.append(f"Sheet write error: {e}")

        logger.info(f"Wrote {len(rows)} rows to tracking sheet")

    def _archive_processed(self, enriched):
        """Save processing results to local JSON archive."""
        logger.info("Archiving results...")

        archive_dir = Path("/data/invoice_archive")
        archive_dir.mkdir(parents=True, exist_ok=True)

        filename = f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = archive_dir / filename

        try:
            filepath.write_text(json.dumps(enriched, indent=2))
        except Exception as e:
            logger.error(f"Archive save failed: {e}")
            self.errors.append(f"Archive error: {e}")

        logger.info(f"Archived to {filepath}")

    # --- Phase 4: Reporting ---

    def _notify_slack_summary(self):
        """Post summary to finance team Slack channel."""
        logger.info("Sending Slack notification...")

        summary = (
            f"*Invoice Sync Complete*\n"
            f"• Fetched: {self.stats['fetched']}\n"
            f"• Matched: {self.stats['matched']}\n"
            f"• Updated: {self.stats['updated']}\n"
            f"• Errors: {self.stats['errors']}"
        )

        if self.errors:
            summary += f"\n\n⚠️ Errors:\n" + "\n".join(f"• {e}" for e in self.errors[:5])

        try:
            requests.post(
                SLACK_WEBHOOK_URL,
                json={"text": summary},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

        logger.info("Slack notification sent")

    def _log_final_stats(self):
        """Log final pipeline statistics."""
        logger.info("=" * 50)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"  Fetched:  {self.stats['fetched']}")
        logger.info(f"  Matched:  {self.stats['matched']}")
        logger.info(f"  Updated:  {self.stats['updated']}")
        logger.info(f"  Errors:   {self.stats['errors']}")
        logger.info("=" * 50)


if __name__ == "__main__":
    pipeline = InvoiceSyncPipeline()
    pipeline.run()
