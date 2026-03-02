"""Date/time tools: current datetime and relative date calculations."""

from datetime import date, datetime, timedelta

from langchain_core.tools import tool

from app.llm.tools._utils import _tool_result


@tool
def get_current_datetime(offset_days: int = 0) -> str:
    """Get the current date and time, plus pre-computed relative date ranges.

    Always call this tool FIRST when:
    - The user interacts with appointments (checking availability, booking, listing).
      Assume users want to book into the future; this tool establishes the current date so only future slots are proposed.
    - The user mentions any relative time expression such as 'today', 'tomorrow',
      'next week', 'next month', 'in two weeks', etc.

    Use the returned dates as inputs to other tools (e.g. get_appointment_availability).

    Args:
        offset_days: Days to add (positive) or subtract (negative) from today.
                     Use 0 for the current date, 1 for tomorrow, 7 for a week from now, -1 for yesterday, etc.
    """
    now = datetime.now()
    today = now.date()
    target = today + timedelta(days=offset_days)

    # Next week: Monday–Sunday of the week after today's week
    days_until_next_monday = (7 - today.weekday()) % 7 or 7
    next_week_start = today + timedelta(days=days_until_next_monday)
    next_week_end = next_week_start + timedelta(days=6)

    # Next month: first–last day of the calendar month after today's
    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1)
    else:
        next_month_start = date(today.year, today.month + 1, 1)
    if next_month_start.month == 12:
        next_month_end = date(next_month_start.year + 1, 1, 1) - timedelta(days=1)
    else:
        next_month_end = date(next_month_start.year, next_month_start.month + 1, 1) - timedelta(days=1)

    return _tool_result({
        "current_date": today.isoformat(),
        "current_time": now.strftime("%H:%M:%S"),
        "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "day_of_week": today.strftime("%A"),
        "target_date": target.isoformat(),
        "target_day_of_week": target.strftime("%A"),
        "offset_days_applied": offset_days,
        "relative_ranges": {
            "tomorrow": (today + timedelta(days=1)).isoformat(),
            "one_week_from_today": (today + timedelta(days=7)).isoformat(),
            "two_weeks_from_today": (today + timedelta(days=14)).isoformat(),
            "next_week": {
                "start": next_week_start.isoformat(),
                "end": next_week_end.isoformat(),
            },
            "next_month": {
                "start": next_month_start.isoformat(),
                "end": next_month_end.isoformat(),
            },
        },
    })
