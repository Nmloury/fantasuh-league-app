#!/usr/bin/env python3
"""
Script to generate weekly recaps for the current week.
Used by GitHub Actions workflow to automatically create recaps.
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from dotenv import load_dotenv
from app.lib.facts import build_facts
from app.lib.recap_llm import insert_recap
from app.lib.yahoo_client import get_session, get_league

load_dotenv()


def main():
    """Generate a weekly recap for the previous week if one doesn't exist (retrospective)."""
    # Get league ID and year from environment
    league_id = os.getenv("YAHOO_LEAGUE_ID_SHORT")
    year = int(os.getenv("YAHOO_LEAGUE_YEAR", "2025"))
    
    if not league_id:
        print("Error: YAHOO_LEAGUE_ID_SHORT environment variable not set")
        sys.exit(1)
    
    # Get Yahoo session and league
    print("Getting Yahoo session...")
    sc = get_session()
    print("Getting league information...")
    lg = get_league(sc, year, league_id)
    
    # Get current week from Yahoo API and calculate previous week
    try:
        current_week = lg.current_week()
        # Generate recap for the previous week (retrospective)
        target_week = current_week - 1
        print(f"Current week: {current_week}")
        print(f"Generating recap for previous week: {target_week}")
    except Exception as e:
        print(f"Error getting current week from Yahoo API: {e}")
        print("Falling back to week 1")
        target_week = 1
    
    # Ensure we don't try to generate a recap for week 0 or negative weeks
    if target_week < 1:
        print("⚠️  Cannot generate recap for week 0 or earlier. Current week is 1 or earlier.")
        return
    
    # Build facts for the target week
    print(f"Building facts for week {target_week}...")
    facts = build_facts(None, target_week)
    print(f"Facts built: {len(facts)} fields")
    
    # Try to insert recap
    print(f"Attempting to generate recap for week {target_week}...")
    recap_id = insert_recap(league_id, target_week, facts)
    
    if recap_id:
        print(f"✅ Successfully generated recap with ID: {recap_id}")
    else:
        print(f"ℹ️  Recap for week {target_week} already exists, skipping generation")


if __name__ == "__main__":
    main()
