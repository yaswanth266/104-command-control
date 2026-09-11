import datetime
from sqlalchemy.orm import Session
from app.models.ticket_assignment import TicketAssignment

def get_chain(db: Session, ticket_id: int):
    """Full assignment history for a ticket, oldest first - the current
    occupant of each level is whichever row for that level has status
    'ACTIVE' (there's at most one, enforced by release_level below)."""
    return (db.query(TicketAssignment)
              .filter(TicketAssignment.ticket_id == ticket_id)
              .order_by(TicketAssignment.assigned_at)
              .all())

def get_active_for_level(db: Session, ticket_id: int, level: str):
    return (db.query(TicketAssignment)
              .filter(TicketAssignment.ticket_id == ticket_id, TicketAssignment.level == level,
                      TicketAssignment.status == "ACTIVE")
              .first())

def release_level(db: Session, ticket_id: int, level: str, now: datetime.datetime = None):
    now = now or datetime.datetime.now()
    db.query(TicketAssignment).filter(
        TicketAssignment.ticket_id == ticket_id, TicketAssignment.level == level, TicketAssignment.status == "ACTIVE"
    ).update({"status": "RELEASED", "released_at": now})

def add_occupant(db: Session, ticket_id: int, level: str, user=None, team_code: str = None,
                  team_name: str = None, source: str = "LOCAL", now: datetime.datetime = None) -> TicketAssignment:
    now = now or datetime.datetime.now()
    row = TicketAssignment(
        ticket_id=ticket_id, level=level,
        user_id=user.id if user else None,
        user_name_snapshot=user.name if user else None,
        team_code=team_code, team_name_snapshot=team_name,
        assigned_at=now, status="ACTIVE", source=source,
    )
    db.add(row)
    return row
