from datetime import datetime
from database.db import get_db


def _date_filter(date_from: str | None, date_to: str | None) -> tuple:
    """Return (clause, params) to append to a 'WHERE user_id = ?' condition."""
    clause, params = "", []
    if date_from:
        clause += " AND date >= ?"
        params.append(date_from)
    if date_to:
        clause += " AND date <= ?"
        params.append(date_to)
    return clause, params


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


def get_summary_stats(user_id: int, date_from: str | None = None, date_to: str | None = None) -> dict:
    """Return total_spent (float), transaction_count (int), top_category (str)."""
    date_clause, date_params = _date_filter(date_from, date_to)
    where = "WHERE user_id = ?" + date_clause
    params = tuple([user_id] + date_params)

    db = get_db()
    base = db.execute(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total FROM expenses " + where,
        params,
    ).fetchone()
    top_row = db.execute(
        "SELECT category, SUM(amount) AS cat_total"
        " FROM expenses " + where +
        " GROUP BY category ORDER BY cat_total DESC LIMIT 1",
        params,
    ).fetchone()
    db.close()
    return {
        "transaction_count": int(base["cnt"]),
        "total_spent": float(base["total"]),
        "top_category": top_row["category"] if top_row else "—",
    }


def get_recent_transactions(user_id: int, limit: int = 10, date_from: str | None = None, date_to: str | None = None) -> list:
    """Return list of dicts (date, description, category, amount), newest-first."""
    date_clause, date_params = _date_filter(date_from, date_to)
    where = "WHERE user_id = ?" + date_clause
    params = tuple([user_id] + date_params + [limit])

    db = get_db()
    rows = db.execute(
        "SELECT date, description, category, amount"
        " FROM expenses " + where +
        " ORDER BY date DESC, id DESC LIMIT ?",
        params,
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


def get_category_breakdown(user_id: int, date_from: str | None = None, date_to: str | None = None) -> list:
    """Return list of dicts (name, amount, pct) summing to 100%, [] if no data."""
    date_clause, date_params = _date_filter(date_from, date_to)
    where = "WHERE user_id = ?" + date_clause
    params = tuple([user_id] + date_params)

    db = get_db()
    rows = db.execute(
        "SELECT category AS name, SUM(amount) AS amount"
        " FROM expenses " + where +
        " GROUP BY category ORDER BY amount DESC",
        params,
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
