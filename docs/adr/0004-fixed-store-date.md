# 0004: Freeze the store date

**Status:** Accepted

## Context
`get_today_date` returned the machine's real date, while the sample purchases and the expected answers in the dataset were written for mid-October 2026. A month later every purchase had drifted past the 30-day window. The agent correctly refused refunds that the dataset still expected, and Answer Correctness scored 0.00 with nothing actually broken. A test that rots with the calendar is not a test.

## Decision
`get_today_date` returns a fixed **store date, 2026-10-16** (`STORE_TODAY`), overridable with `AGENT_TODAY`. It is recorded with every saved evaluation run and shown in the app.

## Consequences
- Answer Correctness went from 0.00 to 1.00 on the same cases, and results are comparable across days.
- Changing the data or `AGENT_TODAY` means updating the expected answers too. The README says so next to the dataset.
