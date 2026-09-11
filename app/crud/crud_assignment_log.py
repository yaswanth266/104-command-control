from sqlalchemy.orm import Session
from app.models.api_assignment_log import ApiAssignmentLog

def log_attempt(db: Session, ticket_id: int, mode: str, request_payload: dict, response_payload: dict,
                 status: str, error_message: str = None) -> ApiAssignmentLog:
    row = ApiAssignmentLog(ticket_id=ticket_id, mode=mode, request_payload=request_payload,
                            response_payload=response_payload, status=status, error_message=error_message)
    db.add(row)
    db.commit()
    return row

def get_logs_for_ticket(db: Session, ticket_id: int):
    return (db.query(ApiAssignmentLog)
              .filter(ApiAssignmentLog.ticket_id == ticket_id)
              .order_by(ApiAssignmentLog.created_at)
              .all())
