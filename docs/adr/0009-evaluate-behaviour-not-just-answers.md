# 0009: Gate quality on behavior metrics, not answer text

**Status:** Accepted

## Context
In one evaluation run, **Answer Correctness scored 1.00** on both refund cases: the agent replied "A refund ticket for $30 has been issued". **Tool Correctness scored 0.75**, though: the agent never called `issue_refund_ticket`. It **told the customer a refund was issued without issuing it.** A test that only checks the answer passes this, and a real customer would never get their money.

The cause was that `calculate_right_refund` returned "the value of the refund is: 30". That reads like a finished result, so the model stopped there.

## Decision
- Rewrite the system prompt as an explicit procedure: history, then date, then quote, then issue, then reply. Add "Never say a ticket was issued unless issue_refund_ticket returned successfully".
- Make the tool contract explicit: the quote tool now says *"Quoted refund amount: 30. No ticket has been issued yet; call issue_refund_ticket(...)"*.
- Treat **Tool Correctness and Argument Correctness as release-blocking**, alongside Answer Correctness.

## Consequences
- After the fix, every refund case calls exactly the expected four tools, and Tool Correctness went from 0.75 to 1.00.
- Tool outputs are part of the prompt surface: wording a tool's result is as important as wording the system prompt.
