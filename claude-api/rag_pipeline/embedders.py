"""A STAND-IN for a real embedding model, so the practice runs offline.

It is NOT a real embedding model. Each dimension is a hand-written "concept"
(a list of word stems that belong together). A text's vector counts how many of
its words fall in each concept. This reproduces the two properties of real
embeddings that matter for the lesson:

  + paraphrases land close together  ("turnover" ~ "attrition" ~ "hybrid work")
  - identifiers carry no meaning     ("INC-2023-Q4-011" matches no concept at all)

To use a real model instead, pass any `str -> list[float]` function to
VectorIndex (see the README).
"""

from typing import Dict, List, Tuple

from indexes import tokenize

CONCEPTS: Dict[str, Tuple[str, ...]] = {
    "security": ("breach", "broke", "break", "hack", "attack", "intru", "unauthori", "exfiltrat", "stole",
                 "steal", "stolen", "phish", "malware", "ransom", "credential", "incident", "threat",
                 "vulnerab", "secur"),
    "software": ("software", "code", "deploy", "release", "rollback", "outage", "crash", "bug", "latency",
                 "engineer", "service", "uptime", "stabil", "server", "database", "api", "performance",
                 "regress", "failure"),
    "finance": ("revenue", "profit", "cash", "margin", "earning", "income", "liquid", "forecast", "budget",
                "cost", "expens", "financ", "capital", "dividend", "invest", "money", "reserve"),
    "legal": ("legal", "law", "lawsuit", "sue", "litigat", "contract", "agreement", "liabil", "indemn",
              "complian", "regulat", "gdpr", "court", "claim", "dispute", "counsel", "attorney"),
    "people": ("employ", "hire", "hiring", "recruit", "attrition", "turnover", "retention", "remote",
               "hybrid", "staff", "talent", "workforce", "headcount", "compensation"),
    "customer": ("customer", "ticket", "support", "complain", "satisf", "churn", "refund", "contact"),
    "logistics": ("supply", "supplier", "vendor", "ship", "logistic", "warehouse", "deliver", "inventory",
                  "freight", "procure"),
    "marketing": ("market", "campaign", "brand", "advertis", "lead", "pipeline", "sales", "conversion",
                  "audience"),
    "sustainability": ("sustainab", "emission", "carbon", "energy", "renewable", "climate", "green",
                       "environment", "esg", "net-zero"),
}
_NAMES = list(CONCEPTS)


def concept_embed(text: str) -> List[float]:
    tokens = tokenize(text)
    return [
        float(sum(1 for t in tokens if any(t.startswith(stem) for stem in CONCEPTS[name])))
        for name in _NAMES
    ]
