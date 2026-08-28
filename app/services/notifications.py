from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.crud.crud_notification import create_notification
from app.crud.crud_settings import get_dispatch_config
from app.crud.crud_user import get_local_team_lead

def notify_new_ticket(db: Session, ticket: Ticket):
    create_notification(db, ticket.team, ticket.id, "NEW_TICKET",
                         f"New {ticket.priority} ticket {ticket.ticket_no}: {(ticket.problem or '')[:120]}")
    if ticket.priority in ("P1", "P2"):
        create_notification(db, ticket.team, ticket.id, "HIGH_PRIORITY",
                             f"{ticket.priority} ticket {ticket.ticket_no} needs prompt attention")
    # Local Team Lead routing (future, dormant until enabled): in ADDITION to
    # the team-wide broadcast above, personally ping the district's lead so
    # they can assign it to an engineer or self-acknowledge it themselves.
    if ticket.district_id and get_dispatch_config(db)["local_team_lead_enabled"]:
        for lead in get_local_team_lead(db, ticket.team, ticket.district_id):
            create_notification(db, None, ticket.id, "NEW_TICKET_LOCAL_LEAD",
                                 f"New {ticket.priority} ticket {ticket.ticket_no} in your district",
                                 audience_username=lead.username)

def notify_escalated(db: Session, ticket: Ticket, note: str):
    create_notification(db, "CC_MANAGER", ticket.id, "ESCALATED",
                         f"Ticket {ticket.ticket_no} escalated by {ticket.team}: {note}")

def notify_assigned(db: Session, ticket: Ticket, assignee_username: str, manager_name: str):
    # audience_role deliberately None - this is addressed to one person ("you
    # were assigned"), not the whole team; setting audience_role=ticket.team
    # here would leak it to every teammate via get_notifications' OR filter.
    create_notification(db, None, ticket.id, "ASSIGNED",
                         f"{manager_name} assigned you ticket {ticket.ticket_no}",
                         audience_username=assignee_username)
