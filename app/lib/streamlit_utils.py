"""
Streamlit utility functions for the Fantasy League application.

This module contains all cached data functions and utilities used across
the Streamlit application pages.
"""

import streamlit as st
from supabase import Client
from typing import Optional, List, Dict, Any, Tuple


# =============================================================================
# WEEK UTILITIES
# =============================================================================

@st.cache_data(show_spinner=False)
def get_current_week(_sb: Client) -> int:
    """Get the most recently completed week from the database.
    
    This value is updated by the ETL process (compute_metrics.py) which gets
    the authoritative current week from the Yahoo Fantasy API.
    
    Args:
        _sb: Supabase client
        
    Returns:
        int: The most recently completed week number
    """
    try:
        result = _sb.table("app_config").select("value").eq("key", "current_week").execute()
        if result.data:
            return int(result.data[0]["value"])
        else:
            st.warning("No current week found in database, defaulting to week 1")
            return 1
    except Exception as e:
        st.error(f"Error getting current week from database: {e}")
        return 1


@st.cache_data(show_spinner=False)
def get_available_weeks(_sb: Client, table_name: str = "matchups") -> List[int]:
    """Get all available weeks from a specific table.
    
    Args:
        _sb: Supabase client
        table_name: Name of the table to query for weeks
        
    Returns:
        List[int]: Sorted list of available weeks (most recent first)
    """
    try:
        result = _sb.table(table_name).select("week").order("week", desc=True).execute()
        if result.data:
            # Get unique weeks and sort them
            weeks = sorted(set(row["week"] for row in result.data), reverse=True)
            return weeks
        else:
            return []
    except Exception as e:
        st.error(f"Error getting available weeks from {table_name}: {e}")
        return []


# =============================================================================
# TEAM AND MANAGER UTILITIES
# =============================================================================

@st.cache_data(show_spinner=False)
def get_team_names(_sb: Client) -> Dict[str, str]:
    """Get mapping of manager_id to team_name.
    
    Args:
        _sb: Supabase client
        
    Returns:
        Dict[str, str]: Mapping of manager_id to team_name
    """
    try:
        result = _sb.table("managers").select("manager_id, team_name").execute()
        return {m["manager_id"]: m["team_name"] for m in result.data}
    except Exception:
        return {}


@st.cache_data(show_spinner=False)
def get_managers_data(_sb: Client) -> List[Dict[str, Any]]:
    """Get all manager data.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: List of manager records
    """
    try:
        result = _sb.table("managers").select("manager_id, manager_name, team_name").execute()
        return result.data
    except Exception:
        return []


# =============================================================================
# RECAP UTILITIES
# =============================================================================

@st.cache_data(show_spinner=False)
def get_recap_for_week(_sb: Client, week: int) -> Optional[Dict[str, Any]]:
    """Get the recap for a specific week.
    
    Args:
        _sb: Supabase client
        week: Week number
        
    Returns:
        Optional[Dict[str, Any]]: Recap for the specified week or None
    """
    try:
        result = _sb.table("recaps").select("*").eq("week", week).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def get_latest_recap(_sb: Client) -> Optional[Dict[str, Any]]:
    """Get the most recent recap from the database.
    
    Args:
        _sb: Supabase client
        
    Returns:
        Optional[Dict[str, Any]]: Most recent recap or None
    """
    
    return get_recap_for_week(_sb, get_current_week(_sb))

@st.cache_data(show_spinner=False)
def get_available_recap_weeks(_sb: Client) -> List[int]:
    """Get all weeks that have recaps available.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[int]: List of weeks with available recaps
    """
    try:
        result = _sb.table("recaps").select("week").order("week", desc=True).execute()
        return [row["week"] for row in result.data] if result.data else []
    except Exception:
        return []


# =============================================================================
# MATCHUP UTILITIES
# =============================================================================

@st.cache_data(show_spinner=False)
def get_closest_matchup(_sb: Client) -> Optional[Tuple[Dict[str, Any], int]]:
    """Get the closest finished matchup from the last completed week.
    
    Args:
        _sb: Supabase client
        
    Returns:
        Optional[Tuple[Dict[str, Any], int]]: Tuple of (matchup_data, week) or None
    """
    try:
        # Get the most recent completed week from our stored value
        week = get_current_week(_sb)
        
        # Get all matchups for that week with actual scores
        matchups = _sb.table("matchups").select("*").eq("week", week).not_.is_("score_a", "null").not_.is_("score_b", "null").or_("score_a.gt.0,score_b.gt.0").execute()
        
        if not matchups.data:
            return None
        
        # Find closest matchup
        closest = None
        min_diff = float('inf')
        
        for matchup in matchups.data:
            diff = abs(matchup["score_a"] - matchup["score_b"])
            if diff < min_diff:
                min_diff = diff
                closest = matchup
        
        return closest, week
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def get_matchups_for_week(_sb: Client, week: int) -> List[Dict[str, Any]]:
    """Get all matchups for a specific week.
    
    Args:
        _sb: Supabase client
        week: Week number
        
    Returns:
        List[Dict[str, Any]]: List of matchups for the specified week
    """
    try:
        result = _sb.table("matchups").select("*").eq("week", week).execute()
        return result.data
    except Exception:
        return []


# =============================================================================
# STANDINGS UTILITIES
# =============================================================================

@st.cache_data(show_spinner=False)
def get_standings(_sb: Client) -> List[Dict[str, Any]]:
    """Get current standings with team names for the last completed week.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: List of standings records with team names, wins, losses, and streaks
    """
    try:
        # Get the most recent completed week from our stored value
        week = get_current_week(_sb)
        
        # Get standings for that week
        standings = _sb.table("v_standings").select("manager_id, cum_wins, cum_pf").eq("week", week).order("cum_wins", desc=True).order("cum_pf", desc=True).execute()
        
        # Get team names
        team_names = get_team_names(_sb)
        
        # Calculate records and streaks
        results = []
        for standing in standings.data:
            manager_id = standing["manager_id"]
            wins = standing["cum_wins"]
            losses = week - wins
            
            # Get recent results for streak calculation (only up to the most recent completed week)
            recent_scores = _sb.table("v_team_week_scores").select("win").eq("manager_id", manager_id).gte("week", max(1, week-4)).lte("week", week).order("week", desc=True).execute()
            
            streak = "—"
            if recent_scores.data:
                streak_wins = 0
                streak_losses = 0
                for score in recent_scores.data:
                    if score["win"]:
                        if streak_losses > 0:
                            break
                        streak_wins += 1
                    else:
                        if streak_wins > 0:
                            break
                        streak_losses += 1
                
                if streak_wins > 0:
                    streak = f"W{streak_wins}"
                elif streak_losses > 0:
                    streak = f"L{streak_losses}"
            
            results.append({
                "team_name": team_names.get(manager_id, manager_id),
                "wins": wins,
                "losses": losses,
                "streak": streak
            })
        
        return results
    except Exception:
        return []


# =============================================================================
# DATA RETRIEVAL UTILITIES
# =============================================================================

@st.cache_data(show_spinner=False)
def get_expected_wins_data(_sb: Client) -> List[Dict[str, Any]]:
    """Get expected wins data.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: Expected wins data
    """
    try:
        result = _sb.table("expected_wins").select("manager_id,cum_xw,week").execute()
        return result.data
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def get_actual_wins_data(_sb: Client) -> List[Dict[str, Any]]:
    """Get actual wins data.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: Actual wins data
    """
    try:
        result = _sb.table("v_actual_wins").select("manager_id,wins").execute()
        return result.data
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def get_lineup_efficiency_data(_sb: Client) -> List[Dict[str, Any]]:
    """Get lineup efficiency data.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: Lineup efficiency data
    """
    try:
        result = _sb.table("lineup_efficiency").select("*").execute()
        return result.data
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def get_faab_roi_data(_sb: Client) -> List[Dict[str, Any]]:
    """Get FAAB ROI data.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: FAAB ROI data
    """
    try:
        result = _sb.table("faab_roi").select("*").execute()
        return result.data
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def get_draft_roi_data(_sb: Client) -> List[Dict[str, Any]]:
    """Get draft ROI data.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: Draft ROI data
    """
    try:
        result = _sb.table("draft_roi").select("*").execute()
        return result.data
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def get_players_data(_sb: Client) -> List[Dict[str, Any]]:
    """Get players data.
    
    Args:
        _sb: Supabase client
        
    Returns:
        List[Dict[str, Any]]: Players data
    """
    try:
        result = _sb.table("players").select("player_id,name").execute()
        return result.data
    except Exception:
        return []


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_team_name_mapping(_sb: Client) -> Dict[str, str]:
    """Create a mapping of manager_id to team_name.
    
    Args:
        _sb: Supabase client
        
    Returns:
        Dict[str, str]: Mapping of manager_id to team_name
    """
    return get_team_names(_sb)


def create_player_name_mapping(_sb: Client) -> Dict[str, str]:
    """Create a mapping of player_id to player name.
    
    Args:
        _sb: Supabase client
        
    Returns:
        Dict[str, str]: Mapping of player_id to player name
    """
    try:
        players_data = get_players_data(_sb)
        return {p["player_id"]: p["name"] for p in players_data}
    except Exception:
        return {}


def format_week_selector(weeks: List[int], default_index: int = 0) -> int:
    """Create a week selector widget.
    
    Args:
        weeks: List of available weeks
        default_index: Index of default selected week
        
    Returns:
        int: Selected week number
    """
    if not weeks:
        return 1
    
    return st.selectbox(
        "Select Week", 
        options=weeks, 
        index=default_index,
        format_func=lambda x: f"Week {x}"
    )
