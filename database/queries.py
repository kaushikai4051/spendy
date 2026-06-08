from datetime import datetime
from database.db import get_db


# ── Sub-agent-2: get_user_by_id ─────────────────────────────────────
def get_user_by_id(user_id: int) -> dict:
    """Return name, email, member_since ('Month YYYY') for user_id."""
    db = get_db()
    row = db.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    db.close()
    if row is None:
        return {"name": "", "email": "", "member_since": "Unknown"}
    try:
        member_since = datetime.strptime(row["created_at"][:10], "%Y-%m-%d").strftime("%B %Y")
    except (ValueError, TypeError):
        member_since = "Unknown"
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }
# END SUB-AGENT-2: get_user_by_id


# ── Sub-agent-2: get_summary_stats ──────────────────────────────────
def get_summary_stats(user_id: int) -> dict:
    """Return total_spent (float), transaction_count (int), top_category (str)."""
    db = get_db()
    base = db.execute(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    top_row = db.execute(
        """SELECT category, SUM(amount) AS cat_total
           FROM expenses
           WHERE user_id = ?
           GROUP BY category
           ORDER BY cat_total DESC
           LIMIT 1""",
        (user_id,),
    ).fetchone()
    db.close()
    return {
        "transaction_count": int(base["cnt"]),
        "total_spent": float(base["total"]),
        "top_category": top_row["category"] if top_row else "—",
    }
# END SUB-AGENT-2: get_summary_stats


# ── Sub-agent-1: get_recent_transactions ────────────────────────────
def get_recent_transactions(user_id: int, limit: int = 10) -> list:
    """Return list of dicts (date, description, category, amount), newest-first."""
    db = get_db()
    rows = db.execute(
        """SELECT date, description, category, amount
           FROM expenses
           WHERE user_id = ?
           ORDER BY date DESC, id DESC
           LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    db.close()
    return [
        {
            "date": row["date"],
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]
# END SUB-AGENT-1: get_recent_transactions


# ── Sub-agent-3: get_category_breakdown ─────────────────────────────
def get_category_breakdown(user_id: int) -> list:
    """Return list of dicts (name, amount, pct) summing to 100%, [] if no data."""
    db = get_db()
    rows = db.execute(
        """SELECT category AS name, SUM(amount) AS amount
           FROM expenses
           WHERE user_id = ?
           GROUP BY category
           ORDER BY amount DESC""",
        (user_id,),
    ).fetchall()
    db.close()
    if not rows:
        return []
    total = sum(float(row["amount"]) for row in rows)
    result = []
    assigned = 0
    for i, row in enumerate(rows):
        amt = float(row["amount"])
        if i < len(rows) - 1:
            pct = int(round(amt / total * 100))
            assigned += pct
        else:
            pct = 100 - assigned
        result.append({"name": row["name"], "amount": amt, "pct": pct})
    return result
# END SUB-AGENT-3: get_category_breakdown
