from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.crud.crud_notification import create_notification

def notify_new_ticket(db: Session, ticket: Ticket):
    create_notification(db, ticket.team, ticket.id, "NEW_TICKET",
                         f"New {ticket.priority} ticket {ticket.ticket_no}: {(ticket.problem or '')[:120]}")
    if ticket.priority in ("P1", "P2"):
        create_notification(db, ticket.team, ticket.id, "HIGH_PRIORITY",
                             f"{ticket.priority} ticket {ticket.ticket_no} needs prompt attention")

def notify_escalated(db: Session, ticket: Ticket, note: str):
    create_notification(db, "CC_MANAGER", ticket.id, "ESCALATED",
                         f"Ticket {ticket.ticket_no} escalated by {ticket.team}: {note}")
