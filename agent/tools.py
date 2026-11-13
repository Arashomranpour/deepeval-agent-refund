import logging
import os

from dotenv import load_dotenv
from langchain.tools import tool

from data import users_data
from objects import PurchaseItem
from tickets import get_store

load_dotenv()

# The demo purchase data in data.py has fixed dates, so "today" is frozen too.
# Otherwise every purchase drifts past the 30-day window and the expected
# answers in evaluations/dataset.py stop being true. Override with AGENT_TODAY.
STORE_TODAY = os.getenv("AGENT_TODAY", "2026-10-16")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s "
)

@tool
def get_user_purchase_history(user: str) -> dict:
    """this tool takes the user username and return a dict of the user purchase history if
    the user exists"""
    logging.info(f"using get_user_purchase_history tool on user: {user}")
    if users_data.get(user):
        return users_data[user]
    return {"status": "there was no username found"}

@tool
def calculate_right_refund(user:str, items:list[PurchaseItem])-> str:
    """Quote how much a refund for these items is worth. This does NOT issue anything:
    call issue_refund_ticket with the quoted amount to actually refund the customer."""

    logging.info(f"using calculate_right_refund tool to get user's: {user} refund")

    if users_data.get(user):

        total_refund = 0

        for item in items:
            if users_data[user].get(item.name):
                total_refund += users_data[user][item.name]["price"]

        return (f"Quoted refund amount: {total_refund}. No ticket has been issued yet; "
                f"call issue_refund_ticket(user={user!r}, refund_amount={total_refund}, "
                f"items={[item.name for item in items]!r}) to refund.")

    return {"status": "there was no username found"}

@tool
def issue_refund_ticket(user: str, refund_amount: float, items: list[str] | None = None) -> str:
    """Issue the refund: open a refund ticket for the support team and return its ticket ID.
    Pass the quoted amount from calculate_right_refund and the names of the refunded items."""

    logging.info(f"using issue_refund_ticket for user: {user}")
    if not users_data.get(user):
        return "No ticket issued: there was no username found."
    try:
        ticket = get_store().create(user=user, amount=refund_amount, items=items)
    except Exception:
        logging.exception("could not save the refund ticket")
        return "No ticket issued: the ticket system is unavailable. Tell the customer to try again later."
    return (f"Refund ticket {ticket['id']} issued successfully for {refund_amount}. "
            "Give the customer this ticket ID.")

@tool
def get_today_date() -> str:
    """Return today's date in YYYY-MM-DD format
    This tool takes no arguments
    only use if a user exist and an item is present for refund"""
    logging.info("using the date tool")
    return STORE_TODAY

# print(get_user_purchase_history.invoke("user123"))
#book = PurchaseItem(name="book")
#pen = PurchaseItem(name="pen")
#print(calculate_right_refund.invoke({"user":"user123",
#                                     "items":[book,pen]}))
#print(issue_refund_ticket.invoke({"user":"user123",  "refund_amount":30}))
#print(get_today_date.invoke("user123"))
