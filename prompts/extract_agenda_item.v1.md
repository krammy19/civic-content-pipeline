You are extracting structured facts from a single agenda item's source
text, taken from a city government meeting document (an agenda, staff
report, or minutes).

Agenda item: {item_title}
Item number: {item_number}

Extract, from the text below, ONLY what is explicitly stated:

- **Motions** made on this item: the motion text, who moved and seconded
  it, its outcome, and the vote tally or roll call if one was recorded.
- **People** named in connection with this item — councilmembers, staff,
  applicants, members of the public who spoke — with their role.
- **Locations** — addresses, parcels, neighborhoods, or districts
  affected by this item.
- **Amounts** — dollar figures tied to this item: costs, fees, grants,
  contract values, budget appropriations.
- **item_type** — the single category that best fits this item: consent,
  public_hearing, action, report, closed_session, ceremonial, or unknown
  if none of those fit.

Rules:

1. Do not infer, summarize, or add anything not explicitly stated in the
   text below. If it isn't there, it isn't in your answer.
2. Every motion, person, location, and amount you extract must carry a
   verbatim `source_text` — copy the exact text span that supports it,
   character for character, not a paraphrase. If you cannot quote it
   verbatim from the text below, leave it out entirely.
3. Give each extracted fact a `confidence` from 0.0 to 1.0 reflecting how
   directly the text supports it. An unambiguous, explicit statement
   should score high; something you had to piece together from context
   should score lower.
4. If a category has nothing to extract, return an empty list for it —
   do not guess or fabricate an entry to fill it.
5. For `provenance.source_document`, use any placeholder value — it will
   be overwritten with the actual document identifier after extraction,
   so don't spend effort trying to get it exactly right.

Source text:

{document_text}
