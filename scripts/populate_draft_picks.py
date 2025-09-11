#!/usr/bin/env python3
"""
One-time script to populate the draft_picks table using Yahoo Fantasy API.

This script fetches draft results from Yahoo Fantasy API and populates
the draft_picks table with manager_id, player_id, and cost information.
"""

import os
import sys
import time
from typing import Dict, Any, List
from dotenv import load_dotenv
import yahoo_fantasy_api as yfa
from app.lib.supa import supa
from app.lib.yahoo_client import get_session, get_league

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

YEAR = int(os.environ.get("YAHOO_LEAGUE_YEAR"))
LEAGUE_ID_SHORT = os.environ.get("YAHOO_LEAGUE_ID_SHORT")

def chunked(seq, n=500):
    """Split sequence into chunks of size n."""
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def populate_draft_picks(sb, lg):
    """
    Fetch draft results from Yahoo Fantasy API and populate draft_picks table.
    
    The draft_picks table stores:
    - manager_id: The team key from Yahoo (references managers.manager_id)
    - player_id: The player ID from Yahoo (references players.player_id) 
    - cost: The draft pick number (1st overall = 1, 2nd overall = 2, etc.)
    
    Args:
        sb: Supabase client
        lg: Yahoo Fantasy League object
    """
    try:
        print("Fetching draft results from Yahoo Fantasy API...")
        time.sleep(0.5)  # Rate limiting
        
        # Get draft results from Yahoo API
        draft_results = lg.draft_results()
        
        if not draft_results:
            print("No draft results found.")
            return
            
        print(f"Found {len(draft_results)} draft picks")
        
        # Prepare rows for database insertion
        rows = []
        skipped_count = 0
        
        for pick in draft_results:
            # Extract relevant information from draft pick
            manager_id = pick.get('team_key')
            player_id = str(pick.get('player_id', ''))
            cost = pick.get('cost', 0)  # Using pick number as cost (draft position)
            
            # Skip if we don't have required data
            if not manager_id or not player_id or cost <= 0:
                print(f"Skipping pick with missing/invalid data: {pick}")
                skipped_count += 1
                continue
                
            rows.append({
                "manager_id": manager_id,
                "player_id": player_id,
                "cost": cost
            })
        
        if skipped_count > 0:
            print(f"Skipped {skipped_count} invalid draft picks")
            
        print(f"Prepared {len(rows)} valid draft pick records")
        
        if not rows:
            print("No valid draft picks to insert.")
            return
        
        # Insert in chunks to avoid overwhelming the database
        total_inserted = 0
        for chunk in chunked(rows, 500):
            try:
                sb.table("draft_picks").upsert(
                    chunk, 
                    on_conflict="manager_id,player_id"
                ).execute()
                total_inserted += len(chunk)
                print(f"Inserted chunk of {len(chunk)} draft picks (total: {total_inserted})")
            except Exception as e:
                print(f"Error inserting chunk: {e}")
                # Continue with next chunk
                continue
        
        print(f"Successfully populated draft_picks table with {total_inserted} records")
        
    except Exception as e:
        print(f"Error fetching draft results: {e}")
        raise

def main():
    """Main function to run the draft picks population script."""
    print("Starting draft picks population process...")
    
    print("Step 1: Initializing Supabase client...")
    sb = supa()
    
    print("Step 2: Getting Yahoo session...")
    sc = get_session()
    print("Session created successfully")
    
    print("Step 3: Getting league information...")
    # Retry mechanism for league creation
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"Retry attempt {attempt + 1}/{max_retries}")
                time.sleep(2 * attempt)  # Exponential backoff
            lg = get_league(sc, YEAR, LEAGUE_ID_SHORT)
            print("League object created successfully")
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print("All retry attempts failed. Exiting.")
                raise
            print("Retrying...")
    
    print("Step 4: Populating draft_picks table...")
    populate_draft_picks(sb, lg)
    
    print("Draft picks population complete!")

if __name__ == "__main__":
    main()
