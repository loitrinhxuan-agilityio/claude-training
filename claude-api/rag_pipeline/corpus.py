"""The document collection to search: a fictional Q4 2023 company report.

Mirrors the lesson's setup (a report split into numbered sections). Two incident
IDs are planted on purpose:
  INC-2023-Q4-011  checkout outage   -> sections 2 and 6
  INC-2023-Q3-004  security breach   -> section 10
Identifiers like these are what semantic search is bad at and BM25 is good at.
Several sections also use different words than a user would (e.g. "attrition" vs
"turnover"), which is what BM25 is bad at and semantic search is good at.
"""

SECTIONS = [
    {"id": "1", "title": "Executive Summary", "content": (
        "Fiscal Q4 2023 was a year-end of consolidation. Revenue grew modestly, the Project Phoenix "
        "platform rebuild reached its stabilization milestone, and leadership prioritized resilience: "
        "a security incident and a checkout outage both tested our response processes. This report "
        "summarizes engineering, finance, people, legal, operations, supply chain, marketing and "
        "sustainability results.")},
    {"id": "2", "title": "Software Engineering: Project Phoenix Stability Enhancements", "content": (
        "Project Phoenix, the rebuild of our order-processing platform, entered its stabilization phase "
        "in Q4. On 14 November a faulty configuration pushed during a routine release triggered cascading "
        "failures across the order service, tracked as INC-2023-Q4-011. Checkout was degraded for 47 "
        "minutes until the team rolled the release back. Follow-up work added canary releases, circuit "
        "breakers and tighter p99 latency alerts, and median checkout latency has since dropped 18 percent.")},
    {"id": "3", "title": "Financial Analysis", "content": (
        "Net income for Q4 reached $4.2 million on revenue of $38.6 million, a 3 percent increase year "
        "over year. Gross margin compressed by 90 basis points because of higher cloud costs. Liquidity "
        "remains strong, with $21 million in the bank and no short-term debt. Management guidance for "
        "next year assumes flat earnings and a smaller capital budget.")},
    {"id": "4", "title": "People and Culture", "content": (
        "Headcount ended the quarter at 212. Voluntary attrition fell to 9 percent annualized, down from "
        "14 percent, after the move to a hybrid schedule and a refreshed compensation band. We hired 18 "
        "engineers and 6 account executives, and the average time to fill an open role improved to 41 days.")},
    {"id": "5", "title": "Legal Developments", "content": (
        "Counsel resolved two contract disputes in Q4 and settled one claim by a former vendor for "
        "$310,000. New data-protection regulations required updates to our privacy notices and processor "
        "agreements. Outstanding exposure relates to an indemnification clause in the Northwind master "
        "services agreement, which a court review is expected to clarify in Q1.")},
    {"id": "6", "title": "Customer Support and Operations", "content": (
        "Ticket volume rose 22 percent in Q4, driven largely by the checkout degradation logged as "
        "INC-2023-Q4-011, which generated 1,350 contacts in a single afternoon. Average first-response "
        "time held at 3 hours thanks to temporary overtime and macros for the most common complaints. "
        "Customer satisfaction dipped to 4.1 out of 5 before recovering in December.")},
    {"id": "7", "title": "Supply Chain and Logistics", "content": (
        "Two key suppliers missed delivery windows in November, delaying hardware shipments by an average "
        "of 12 days. We qualified an alternate freight partner, raised safety stock for scanners and "
        "tablets, and renegotiated service levels with our largest vendor. Warehouse inventory turns "
        "improved to 6.1.")},
    {"id": "8", "title": "Marketing and Sales", "content": (
        "The holiday campaign drove a 31 percent rise in qualified leads. Paid search efficiency improved "
        "after we consolidated audiences, and the sales pipeline closed the quarter at 2.4 times target. "
        "Brand awareness among mid-market buyers reached 38 percent in the latest survey.")},
    {"id": "9", "title": "Sustainability", "content": (
        "Our data centers moved to 70 percent renewable electricity, cutting Scope 2 emissions by 26 "
        "percent. We committed to a net-zero target for 2040 and began tracking carbon intensity per "
        "order. Office energy use fell 11 percent after the lighting retrofit.")},
    {"id": "10", "title": "Cybersecurity Analysis: Incident Response Report", "content": (
        "In October an attacker used phished credentials to gain unauthorized access to a reporting "
        "database (INC-2023-Q3-004). About 12,000 customer records were exfiltrated before alerts fired. "
        "The security team revoked the credentials, rotated keys, notified affected customers within 72 "
        "hours, and rolled out hardware security keys for all staff. Detection time fell from 9 days to "
        "6 hours after new monitoring went live.")},
]
