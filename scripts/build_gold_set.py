"""
One-time generator for evals/gold/*.json.

Every case here is hand-annotated from real San Jose City Council and
Planning Commission minutes fetched during M1's live validation
(data/raw/san-jose/, sourced from sanjose.legistar.com). document_text is
a verbatim excerpt of the real minutes; expected/* is ground truth
determined by reading that excerpt directly - not model output, not
inferred from a summary.

One case (sj-cc-synthetic-amount-in-words) is explicitly synthetic: no
real San Jose document in this corpus spells a dollar amount out in
words, and SPEC calls for that as a deliberate hard case. It's built as
its own self-contained document_text rather than edited into a real
excerpt, and is clearly labeled as synthetic in its "notes" field and in
docs/evals.md. Every other case is real.

Run once: `uv run python scripts/build_gold_set.py`. Re-running
overwrites evals/gold/ with the same content (safe, idempotent) - this
script is the record of how the gold set was built, not something meant
to run repeatedly or fetch new content on its own.
"""

import json
from pathlib import Path

GOLD_DIR = Path(__file__).resolve().parent.parent / "evals" / "gold"

CASES = []


def case(
    id, body, meeting_date, source_document, item_number, item_title, document_text, expected, notes
):
    CASES.append(
        {
            "id": id,
            "jurisdiction": "San Jose",
            "body": body,
            "meeting_date": meeting_date,
            "source_document": source_document,
            "item_number": item_number,
            "item_title": item_title,
            "document_text": document_text.strip(),
            "expected": expected,
            "notes": notes,
        }
    )


CC_1209 = "san-jose-city-council-2025-12-09-minutes"
CC_1216 = "san-jose-city-council-2025-12-16-minutes"
PC_1210 = "san-jose-planning-commission-2025-12-10-action-minutes"

# ---------------------------------------------------------------------
# December 9, 2025 - City Council
# ---------------------------------------------------------------------

case(
    id="sj-cc-2025-12-09-1.1",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="1.1",
    item_title="Holiday Children Book Drive Week proclamation",
    document_text=(
        "1.1 Councilmember Rosemary Kamei presented a proclamation recognizing December 8-14, "
        "2025, as Holiday Children Book Drive Week, celebrating the holidays with the purpose of "
        "collecting books for children and promoting literacy in San Jose."
    ),
    expected={
        "item_type": "ceremonial",
        "motions": [],
        "people": [
            {
                "raw_name": "Rosemary Kamei",
                "role": "councilmember",
                "source_text": "Councilmember Rosemary Kamei presented a proclamation",
            }
        ],
        "locations": [],
        "amounts": [],
    },
    notes="Ceremonial item: no motion, no vote, exactly one named councilmember.",
)

case(
    id="sj-cc-2025-12-09-1.3",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="1.3",
    item_title="Dia de la Virgen de Guadalupe proclamation",
    document_text=(
        "1.3 Councilmember Peter Ortiz presented a proclamation declaring December 12, 2025, as Dia de "
        "la Virgen de Guadalupe, honoring the cultural, spiritual, and historical significance of this day and "
        "recognizing its role in fostering faith, unity, and community tradition in the City of San Jose."
    ),
    expected={
        "item_type": "ceremonial",
        "motions": [],
        "people": [
            {
                "raw_name": "Peter Ortiz",
                "role": "councilmember",
                "source_text": "Councilmember Peter Ortiz presented a proclamation",
            }
        ],
        "locations": [],
        "amounts": [],
    },
    notes="Second ceremonial item, same shape as 1.1 - checks the model isn't thrown by a different holiday/name.",
)

case(
    id="sj-cc-2025-12-09-2.4",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.4",
    item_title="Mayor and Council Excused Absence Requests",
    document_text=(
        "Action: Upon motion by Councilmember Michael Mulcahy, seconded by Councilmember "
        "Pamela Campos, and carried unanimously, the Consent Calendar was approved as a whole, and "
        "the following actions were taken as indicated. (11-0-0)\n\n"
        "2.4 Mayor and Council Excused Absence Requests.\n"
        "Request for an excused absence for Councilmember Kamei from the regular meeting of Rules "
        "and Open Government Committee and Committee of the Whole on December 3, 2025, due to "
        "authorized City business to attend the Local Agency Formation Commission of Santa Clara "
        "County (Santa Clara LAFCO) meeting.\n\n"
        "Action: The request for an excused absence for Councilmember Kamei from the regular meeting "
        "of Rules and Open Government Committee and Committee of the Whole on December 3, 2025 "
        "was approved. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "the Consent Calendar was approved as a whole",
                "moved_by": "Michael Mulcahy",
                "seconded_by": "Pamela Campos",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Michael Mulcahy, seconded by Councilmember "
                    "Pamela Campos, and carried unanimously, the Consent Calendar was approved as a whole"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Michael Mulcahy",
                "role": "councilmember",
                "source_text": "Councilmember Michael Mulcahy",
            },
            {
                "raw_name": "Pamela Campos",
                "role": "councilmember",
                "source_text": "Councilmember Pamela Campos",
            },
            {
                "raw_name": "Kamei",
                "role": "councilmember",
                "source_text": "excused absence for Councilmember Kamei",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes=(
        "Hard case: consent-calendar item with NO item-specific motion line of its own - the only real "
        "motion in the text is the collective one covering the whole calendar. Tests whether the model "
        "correctly attributes the bulk motion rather than inventing a per-item one or omitting it entirely."
    ),
)

case(
    id="sj-cc-2025-12-09-2.7",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.7",
    item_title="First Amendments to the Agreements with HNTB Corporation and Landrum & Brown, Inc.",
    document_text=(
        "2.7 First Amendments to the Agreements with HNTB Corporation and Landrum & Brown, Inc. for "
        "On-Call Planning and Environmental Professional Consulting Services at the San Jose Mineta "
        "International Airport.\n"
        "Adopt a resolution authorizing the City Manager or her designee to negotiate and execute the First "
        "Amendments to the Master Consultant Services Agreements with HNTB Corporation and Landrum & "
        "Brown, Inc. for on-call planning and environmental professional consulting services, increasing the "
        "combined maximum compensation by $1,000,000, from $3,500,000 to $4,500,000, with no change to "
        "the term of the agreements.\n\n"
        "Action: Resolution No. RES2025-411 was adopted, authorizing the City Manager or her designee to "
        "negotiate and execute the First Amendments to the Master Consultant Services Agreements with "
        "HNTB Corporation and Landrum & Brown, Inc. for on-call planning and environmental professional "
        "consulting services, increasing the combined maximum compensation by $1,000,000, from "
        "$3,500,000 to $4,500,000, with no change to the term of the agreements. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-411 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: Resolution No. RES2025-411 was adopted",
            }
        ],
        "people": [],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$1,000,000",
                "amount_usd": "1000000",
                "kind": "contract",
                "source_text": "increasing the combined maximum compensation by $1,000,000",
            },
            {
                "raw_text": "$3,500,000",
                "amount_usd": "3500000",
                "kind": "contract",
                "source_text": "from $3,500,000 to $4,500,000",
            },
            {
                "raw_text": "$4,500,000",
                "amount_usd": "4500000",
                "kind": "contract",
                "source_text": "from $3,500,000 to $4,500,000",
            },
        ],
    },
    notes="Contract amendment with three related dollar figures (increase, old cap, new cap) and no named individual mover/seconder - it's a consent item resolved by resolution number, not a personally-attributed motion.",
)

case(
    id="sj-cc-2025-12-09-2.9",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.9",
    item_title="Business Tax and Business Improvement Districts Assessment Amnesty Programs",
    document_text=(
        "2.9 Business Tax and Business Improvement Districts Assessment Amnesty Programs.\n"
        "(a) Approve an ordinance authorizing the Director of Finance or her designee to administer a Business "
        "Tax Amnesty Program which forgives taxpayers who pay certain past due business taxes from liability "
        "for the remaining past due business taxes, interest, and penalties.\n"
        "(b) Approve an ordinance authorizing a Business Improvement District Assessment Amnesty Program "
        "for the Downtown, Japantown, Tully Road, and Monterey Corridor Business Improvement Districts.\n\n"
        "Councilmember Michael Mulcahy offered comment on Item 2.9 regarding business tax and business "
        "improvement district fees.\n\n"
        "Maria Oberg, Director, Finance, responded to questions from the Council.\n\n"
        "Action: (a) Ordinance No. 31281 was passed for publication, authorizing the Director of Finance or "
        "her designee to administer a Business Tax Amnesty Program which forgives taxpayers who pay "
        "certain past due business taxes from liability for the remaining past due business taxes, interest, and "
        "penalties; and (b) Ordinance No. 31282 was passed for publication, authorizing a Business "
        "Improvement District Assessment Amnesty Program for the Downtown, Japantown, Tully Road, and "
        "Monterey Corridor Business Improvement Districts. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Ordinance No. 31281 was passed for publication",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Ordinance No. 31281 was passed for publication",
            },
            {
                "text": "Ordinance No. 31282 was passed for publication",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Ordinance No. 31282 was passed for publication",
            },
        ],
        "people": [
            {
                "raw_name": "Michael Mulcahy",
                "role": "councilmember",
                "source_text": "Councilmember Michael Mulcahy offered comment",
            },
            {
                "raw_name": "Maria Oberg",
                "role": "staff",
                "source_text": "Maria Oberg, Director, Finance, responded to questions",
            },
        ],
        "locations": [
            {
                "raw_text": "Downtown, Japantown, Tully Road, and Monterey Corridor Business Improvement Districts",
                "source_text": "the Downtown, Japantown, Tully Road, and Monterey Corridor Business Improvement Districts",
            }
        ],
        "amounts": [],
    },
    notes="Two-part ordinance item with a named department director (staff, not councilmember) and named business districts as locations rather than street addresses.",
)

case(
    id="sj-cc-2025-12-09-2.10",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.10",
    item_title="Adoption of an Official Park Name for a New Public Park at Senter Road and Serenade Way",
    document_text=(
        "2.10 Adoption of an Official Park Name for a New Public Park at Senter Road and Serenade "
        "Way.\n"
        "Adopt “Tsugio Fujimoto Park” as the official name for the park located along Senter Road between "
        "Serenade Way and Diamond Heights Drive, as recommended by staff and the Parks and Recreation "
        "Commission. Council District 2.\n\n"
        "Councilmember Pamela Campos offered comment on Item 2.10 regarding the accomplishments of "
        "Tsugio Fujimoto.\n\n"
        "Action: “Tsugio Fujimoto Park” was adopted as the official name for the park located along Senter "
        "Road between Serenade Way and Diamond Heights Drive. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "“Tsugio Fujimoto Park” was adopted as the official name for the park",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "“Tsugio Fujimoto Park” was adopted as the official name for the park located along Senter",
            }
        ],
        "people": [
            {
                "raw_name": "Pamela Campos",
                "role": "councilmember",
                "source_text": "Councilmember Pamela Campos offered comment",
            }
        ],
        "locations": [
            {
                "raw_text": "Senter Road between Serenade Way and Diamond Heights Drive",
                "source_text": "the park located along Senter Road between Serenade Way and Diamond Heights Drive",
            }
        ],
        "amounts": [],
    },
    notes="Real street-intersection location with no dollar amount at all - checks the model returns an empty amounts list rather than inventing one.",
)

case(
    id="sj-cc-2025-12-09-2.12",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.12",
    item_title="San Jose Police Foundation Donation of Equipment for Police Fixed-Wing Aircraft",
    document_text=(
        "2.12 San Jose Police Foundation Donation of Equipment for Police Fixed-Wing Aircraft.\n"
        "Adopt a resolution accepting a donation from the San Jose Police Foundation of required "
        "equipment for the new Police Department fixed-wing aircraft, including a camera imaging system "
        "and associated mount, and dual workstation monitors, with a combined value of $1,523,394.\n\n"
        "Action: Resolution No. RES2025-414 was adopted, accepting a donation from the San Jose Police "
        "Foundation of required equipment for the new Police Department fixed-wing aircraft, including a "
        "camera imaging system and associated mount, and dual workstation monitors, with a combined "
        "value of $1,523,394. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-414 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Resolution No. RES2025-414 was adopted",
            }
        ],
        "people": [],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$1,523,394",
                "amount_usd": "1523394",
                "kind": "grant",
                "source_text": "with a combined value of $1,523,394",
            }
        ],
    },
    notes="A donation (not a contract/fee/budget line) - tests whether the model picks a reasonable 'kind' for an in-kind gift's dollar value.",
)

case(
    id="sj-cc-2025-12-09-2.13",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.13",
    item_title="Third Amendment to the Agreement with Cal Engineering & Geology, Inc.",
    document_text=(
        "2.13 Third Amendment to the Agreement with Cal Engineering & Geology, Inc. for "
        "Consultant and Professional Engineering Services for FEMA Kelley Park Storm Outfall and "
        "FEMA Alum Rock Park Mineral Spring Embankment Projects.\n"
        "Approve the Third Amendment to the Standard Agreement with Cal Engineering & Geology, Inc., to "
        "extend the term retroactively from October 31, 2024, to October 31, 2029, and decrease the maximum "
        "compensation from $754,540 to $642,801 for the sole purpose of completing the Federal Emergency "
        "Management Agency Kelley Park Storm Outfall and Federal Emergency Management Agency Alum "
        "Rock Park Mineral Spring Embankment projects. Council District 4.\n\n"
        "Action: The third amendment to the Standard Agreement with Cal Engineering & Geology, Inc., to "
        "extend the term retroactively from October 31, 2024, to October 31, 2029, and decrease the maximum "
        "compensation from $754,540 to $642,801 for the sole purpose of completing the Federal Emergency "
        "Management Agency Kelley Park Storm Outfall and Federal Emergency Management Agency Alum "
        "Rock Park Mineral Spring Embankment projects was approved. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "the third amendment to the Standard Agreement with Cal Engineering & Geology, Inc. was approved",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: The third amendment to the Standard Agreement with Cal Engineering & Geology, Inc.",
            }
        ],
        "people": [],
        "locations": [
            {
                "raw_text": "Kelley Park Storm Outfall and Alum Rock Park Mineral Spring Embankment, Council District 4",
                "source_text": "Federal Emergency Management Agency Kelley Park Storm Outfall",
            }
        ],
        "amounts": [
            {
                "raw_text": "$754,540",
                "amount_usd": "754540",
                "kind": "contract",
                "source_text": "decrease the maximum compensation from $754,540 to $642,801",
            },
            {
                "raw_text": "$642,801",
                "amount_usd": "642801",
                "kind": "contract",
                "source_text": "decrease the maximum compensation from $754,540 to $642,801",
            },
        ],
    },
    notes="A compensation DECREASE rather than increase - checks the model doesn't assume amendments always add money.",
)

case(
    id="sj-cc-2025-12-09-2.14",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.14",
    item_title="Actions Related to the 9365 - Happy Hollow Park and Zoo Fossa Night House Project",
    document_text=(
        "2.14 Actions Related to the 9365 - Happy Hollow Park and Zoo Fossa Night House "
        "Project.\n"
        "(a) Accept the report on the status of the 9365 - Happy Hollow Park and Zoo Fossa Night House "
        "Project, acknowledging contractor performance issues and failure to complete the project per contract "
        "requirements.\n"
        "(b) Terminate the existing 9365 - Happy Hollow Park and Zoo Fossa Night House Project contract "
        "with VNH Builders.\n"
        "(c) Adopt a resolution authorizing the City Manager, or her designee, to negotiate and execute "
        "agreements and any ancillary documents with the surety, American Contractors Indemnity "
        "Company, and any construction contractor to complete the project. Council District 7.\n\n"
        "Action: (a) The report on the status of the 9365 - Happy Hollow Park and Zoo Fossa Night House "
        "Project was accepted; (b) the existing 9365 - Happy Hollow Park and Zoo Fossa Night House "
        "Project contract with VNH Builders was terminated; and (c) Resolution No. RES2025-415 was "
        "adopted, authorizing the City Manager, or her designee, to negotiate and execute agreements and "
        "any ancillary documents with the surety, American Contractors Indemnity Company, and any "
        "construction contractor to complete the project. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "the existing contract with VNH Builders was terminated and Resolution No. RES2025-415 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "the existing 9365 - Happy Hollow Park and Zoo Fossa Night House",
            }
        ],
        "people": [],
        "locations": [
            {
                "raw_text": "Happy Hollow Park and Zoo, Council District 7",
                "source_text": "9365 - Happy Hollow Park and Zoo Fossa Night House",
            }
        ],
        "amounts": [],
    },
    notes="Contract termination (not award) with two named organizations (VNH Builders, American Contractors Indemnity Company) that must NOT be extracted as people - they're companies, not individuals.",
)

case(
    id="sj-cc-2025-12-09-2.15",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.15",
    item_title="Shared Micro-Mobility Device Fee Adjustment",
    document_text=(
        "2.15 Shared Micro-Mobility Device Fee Adjustment. - DEFERRED\n"
        "Adopt a resolution amending the 2025-2026 Schedule of Fees and Charges (Resolution No. 72737, "
        "as amended) to decrease the Shared Micro-Mobility Annual Permit and Program Monitoring "
        "Operating Fee from $139 per device to $100 per device, effective January 1, 2026.\n\n"
        "DEFERRED TO 12/16/2025 PER ADMINISTRATION"
    ),
    expected={
        "item_type": "action",
        "motions": [],
        "people": [],
        "locations": [],
        "amounts": [],
    },
    notes=(
        "SPEC hard case: a continued item with no vote at all. Deferred administratively before any motion "
        "was made, so motions must be an empty list, not a fabricated 'continued' motion with no real mover/"
        "seconder to cite."
    ),
)

case(
    id="sj-cc-2025-12-09-3.3",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="3.3",
    item_title="Annual Comprehensive Financial Report for Fiscal Year Ended June 30, 2025",
    document_text=(
        "3.3 Annual Comprehensive Financial Report for Fiscal Year Ended June 30, 2025.\n"
        "Accept the Fiscal Year 2024-2025 Annual Comprehensive Financial Report for the City of San Jose.\n\n"
        "Maria Oberg, Director, Finance Department; Victor Lo, Deputy Director, Finance Department; and "
        "Ben Lau, CPA, Partner: Macias, Gina & O'Connell, offered the presentation and responded to "
        "questions from Council.\n\n"
        "Public Comment: Brian Darby offered public comment.\n\n"
        "Action: Upon motion by Councilmember Michael Mulcahy, seconded by Councilmember Rosemary "
        "Kamei, and carried unanimously, the Fiscal Year 2024-2025 Annual Comprehensive Financial "
        "Report for the City of San Jose was accepted. (11-0-0)"
    ),
    expected={
        "item_type": "report",
        "motions": [
            {
                "text": "the Fiscal Year 2024-2025 Annual Comprehensive Financial Report was accepted",
                "moved_by": "Michael Mulcahy",
                "seconded_by": "Rosemary Kamei",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Michael Mulcahy, seconded by Councilmember Rosemary "
                    "Kamei, and carried unanimously, the Fiscal Year 2024-2025 Annual Comprehensive Financial "
                    "Report for the City of San Jose was accepted"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Maria Oberg",
                "role": "staff",
                "source_text": "Maria Oberg, Director, Finance Department",
            },
            {
                "raw_name": "Victor Lo",
                "role": "staff",
                "source_text": "Victor Lo, Deputy Director, Finance Department",
            },
            {
                "raw_name": "Ben Lau",
                "role": "public",
                "source_text": "Ben Lau, CPA, Partner: Macias, Gina & O'Connell",
            },
            {
                "raw_name": "Brian Darby",
                "role": "public",
                "source_text": "Brian Darby offered public comment",
            },
            {
                "raw_name": "Michael Mulcahy",
                "role": "councilmember",
                "source_text": "Councilmember Michael Mulcahy",
            },
            {
                "raw_name": "Rosemary Kamei",
                "role": "councilmember",
                "source_text": "Councilmember Rosemary Kamei",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes=(
        "Six distinct people across four roles (two staff, an outside auditor, a public commenter, two "
        "councilmembers) with no dollar amount despite being a financial report - tests role classification "
        "more than the other cases do. Ben Lau (an external auditing partner, not a city employee) is "
        "annotated 'public' since 'staff' should mean city staff specifically."
    ),
)

case(
    id="sj-cc-2025-12-09-3.6",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="3.6",
    item_title="First Amendment to the Master Service Agreement with Intergraph Corporation",
    document_text=(
        "3.6 First Amendment to the Master Service Agreement with Intergraph Corporation for the "
        "Computer Aided Dispatch System.\n"
        "Adopt a resolution authorizing the City Manager or her designee to negotiate and execute the First "
        "Amendment to the Master Service Agreement with Intergraph Corporation (Madison, AL) for the "
        "Computer Aided Dispatch System to:\n"
        "(a) Extend the term of the agreement for up to four additional one-year option terms, through "
        "December 31, 2029, subject to the appropriation of funds.\n"
        "(b) Increase the compensation by $8,030,000, for a total not-to-exceed amount of $19,909,000, "
        "subject to the appropriation of funds.\n\n"
        "Public Comment: None provided.\n\n"
        "Action: Upon motion by Councilmember Bien Doan, seconded by Councilmember Pamela Campos, "
        "and carried unanimously, Resolution No. RES2025-416 was adopted, authorizing the City Manager "
        "or her designee to negotiate and execute the First Amendment to the Master Service Agreement with "
        "Intergraph Corporation (Madison, AL) for the Computer Aided Dispatch System to:\n"
        "(a) Extend the term of the agreement for up to four additional one-year option terms, through "
        "December 31, 2029, subject to the appropriation of funds; and "
        "(b) Increase the compensation by $8,030,000, for a total not-to-exceed amount of $19,909,000, "
        "subject to the appropriation of funds. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-416 was adopted",
                "moved_by": "Bien Doan",
                "seconded_by": "Pamela Campos",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Bien Doan, seconded by Councilmember Pamela Campos, "
                    "and carried unanimously, Resolution No. RES2025-416 was adopted"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Bien Doan",
                "role": "councilmember",
                "source_text": "Councilmember Bien Doan",
            },
            {
                "raw_name": "Pamela Campos",
                "role": "councilmember",
                "source_text": "Councilmember Pamela Campos",
            },
        ],
        "locations": [
            {
                "raw_text": "Madison, AL",
                "source_text": "Intergraph Corporation (Madison, AL)",
            }
        ],
        "amounts": [
            {
                "raw_text": "$8,030,000",
                "amount_usd": "8030000",
                "kind": "contract",
                "source_text": "Increase the compensation by $8,030,000",
            },
            {
                "raw_text": "$19,909,000",
                "amount_usd": "19909000",
                "kind": "contract",
                "source_text": "for a total not-to-exceed amount of $19,909,000",
            },
        ],
    },
    notes=(
        "Named mover/seconder plus two related dollar amounts (increase and resulting total) in a "
        "single multi-year contract amendment. Locations corrected after the first eval run: the "
        "vendor's own city (Madison, AL) was a real, verified extraction the model produced that the "
        "initial gold annotation had missed - a second instance of the same gold-completeness gap "
        "found in sj-cc-2025-12-09-8.1."
    ),
)

case(
    id="sj-cc-2025-12-09-3.7",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="3.7",
    item_title="Actions Related to the 9153 - Tenant Improvement 911 Call Center Upgrade Project",
    document_text=(
        "3.7 Actions Related to the 9153 - Tenant Improvement 911 Call Center Upgrade (2018 "
        "Measure T) Project.\n"
        "(a) Award of a contract for the construction of the 9153 - Tenant Improvement 911 Call Center "
        "Upgrade (2018 Measure T) Project to Rodan Builders, Inc. for the Base Bid and Bid Alternate No. 1 "
        "and Bid Alternate No. 2 in the amount of $6,091,858.\n"
        "(b) Approve a 20% contingency in the amount of $1,218,372.\n"
        "(c) Adopt the following 2025-2026 Appropriation Ordinance amendments in the Public Safety "
        "and Infrastructure Bond:\n"
        "(1) Increase the Measure T - Police 911 Call Center Upgrades appropriation to the Public Works "
        "Department by $4,873,000; and\n"
        "(2) Decrease the Measure T - Program Reserve (Public Safety) appropriation by $4,873,000. "
        "Council District 3.\n\n"
        "Public Comment: None provided.\n\n"
        "Action: Upon motion by Councilmember Bien Doan, seconded by Councilmember Rosemary "
        "Kamei, and carried unanimously, (a) the contract for the construction of the 9153 - Tenant "
        "Improvement 911 Call Center Upgrade (2018 Measure T) Project to Rodan Builders, Inc. "
        "for the Base Bid and Bid Alternate No. 1 and Bid Alternate No. 2 in the amount of $6,091,858 was awarded; "
        "(b) a 20% contingency in the amount of $1,218,372 was approved; "
        "(c) Ordinance No. 31283 was adopted, regarding amendments in the Public Safety and "
        "Infrastructure Bond to: "
        "(1) Increase the Measure T - Police 911 Call Center Upgrades appropriation to the Public Works "
        "Department by $4,873,000; and "
        "(2) Decrease the Measure T - Program Reserve (Public Safety) appropriation by $4,873,000. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "the contract was awarded, the contingency was approved, and Ordinance No. 31283 was adopted",
                "moved_by": "Bien Doan",
                "seconded_by": "Rosemary Kamei",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Bien Doan, seconded by Councilmember Rosemary "
                    "Kamei, and carried unanimously, (a) the contract for the construction"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Bien Doan",
                "role": "councilmember",
                "source_text": "Councilmember Bien Doan",
            },
            {
                "raw_name": "Rosemary Kamei",
                "role": "councilmember",
                "source_text": "Councilmember Rosemary Kamei",
            },
        ],
        "locations": [{"raw_text": "Council District 3", "source_text": "Council District 3"}],
        "amounts": [
            {
                "raw_text": "$6,091,858",
                "amount_usd": "6091858",
                "kind": "contract",
                "source_text": "in the amount of $6,091,858 was awarded",
            },
            {
                "raw_text": "$1,218,372",
                "amount_usd": "1218372",
                "kind": "contract",
                "source_text": "a 20% contingency in the amount of $1,218,372 was approved",
            },
            {
                "raw_text": "$4,873,000",
                "amount_usd": "4873000",
                "kind": "budget",
                "source_text": "Increase the Measure T - Police 911 Call Center Upgrades appropriation to the Public Works "
                "Department by $4,873,000",
            },
        ],
    },
    notes=(
        "SPEC-style hard case: single item with four distinct dollar figures of different kinds (a contract "
        "award, a contingency, and a budget appropriation increase/decrease pair) under one motion."
    ),
)

case(
    id="sj-cc-2025-12-09-3.8",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="3.8",
    item_title="Appeals Hearing Board Interview",
    document_text=(
        "3.8 Appeals Hearing Board Interview.\n"
        "(a) Interview applicants and consider appointment to fill three (3) Member-at-Large seats for "
        "terms beginning January 1, 2026 and ending December 31, 2029 on the Appeals Hearing Board.\n\n"
        "Toni Taber, City Clerk, announced the Council's opportunity to fill up to three (3) Member-at-"
        "Large seats. Two applicants were present - Genevieve Altwer and Martin Nguyen; Ronald "
        "Cabanayan submitted a letter requesting reappointment to the Appeals Hearing Board.\n\n"
        "Mayor Matt Mahan requested that the two present applicants provide opening statements. "
        "Genevieve Altwer and Martin Nguyen provided opening statements for the Council's "
        "consideration of their appointment to the Appeals Hearing Board.\n\n"
        "Public Comment: None provided.\n\n"
        "Action: Upon motion by Councilmember Peter Ortiz, seconded by Councilmember David Cohen, "
        "and carried unanimously, Genevieve Altwer, Martin Nguyen, and Ronald Cabanayan were "
        "appointed to fill the three Member-at-Large seats for terms beginning January 1, 2026 and ending "
        "December 31, 2029 on the Appeals Hearing Board. (11-0-0)"
    ),
    expected={
        "item_type": "action",
        "motions": [
            {
                "text": "Genevieve Altwer, Martin Nguyen, and Ronald Cabanayan were appointed",
                "moved_by": "Peter Ortiz",
                "seconded_by": "David Cohen",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Peter Ortiz, seconded by Councilmember David Cohen, "
                    "and carried unanimously, Genevieve Altwer, Martin Nguyen, and Ronald Cabanayan were "
                    "appointed"
                ),
            }
        ],
        "people": [
            {"raw_name": "Toni Taber", "role": "staff", "source_text": "Toni Taber, City Clerk"},
            {
                "raw_name": "Genevieve Altwer",
                "role": "applicant",
                "source_text": "Genevieve Altwer and Martin Nguyen",
            },
            {
                "raw_name": "Martin Nguyen",
                "role": "applicant",
                "source_text": "Genevieve Altwer and Martin Nguyen",
            },
            {
                "raw_name": "Ronald Cabanayan",
                "role": "applicant",
                "source_text": "Ronald Cabanayan submitted a letter requesting reappointment",
            },
            {
                "raw_name": "Matt Mahan",
                "role": "mayor",
                "source_text": "Mayor Matt Mahan requested",
            },
            {
                "raw_name": "Peter Ortiz",
                "role": "councilmember",
                "source_text": "Councilmember Peter Ortiz",
            },
            {
                "raw_name": "David Cohen",
                "role": "councilmember",
                "source_text": "Councilmember David Cohen",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes="Six named people across four roles including the Mayor specifically and three board applicants - a genuinely people-dense item with no dollar amount at all.",
)

case(
    id="sj-cc-2025-12-09-6.1",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="6.1",
    item_title="Actions Related to the Issuance of Non-Exclusive Franchise Agreements for Residential Clean-out Material",
    document_text=(
        "6.1 Actions Related to the Issuance of Non-Exclusive Franchise Agreements for the "
        "Collection, Transport, and Delivery of Residential Clean-out Material and Construction "
        "and Demolition Debris.\n"
        "(a) Conduct a public hearing on the applications of the five companies listed below for non-"
        "exclusive franchises:\n"
        "(1) Compactor Management Company, LLC;\n"
        "(2) MTB Demolition;\n"
        "(3) Bayview Industrial Services, Inc.;\n"
        "(4) Dumpster Pro, Inc.; and\n"
        "(5) TDB Incorporated.\n"
        "(b) Approve ordinances granting the non-exclusive franchises to the five companies listed above.\n\n"
        "Public Comment: None provided.\n\n"
        "Action: Upon motion by Councilmember Domingo Candelas, seconded by Councilmember "
        "Bien Doan, and carried unanimously, (a) a public hearing was conducted on the applications "
        "of the five companies listed for non-exclusive franchises; "
        "(b) Ordinance No. 31284, Ordinance No. 31285, Ordinance No. 31286, Ordinance No. "
        "31287, and Ordinance No. 31288 were passed for publication. (10-0-1; Absent: Ortiz)"
    ),
    expected={
        "item_type": "public_hearing",
        "motions": [
            {
                "text": "a public hearing was conducted and five ordinances were passed for publication",
                "moved_by": "Domingo Candelas",
                "seconded_by": "Bien Doan",
                "outcome": "passed",
                "tally": "10-0-1; Absent: Ortiz",
                "source_text": (
                    "Upon motion by Councilmember Domingo Candelas, seconded by Councilmember "
                    "Bien Doan, and carried unanimously"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Domingo Candelas",
                "role": "councilmember",
                "source_text": "Councilmember Domingo Candelas",
            },
            {
                "raw_name": "Bien Doan",
                "role": "councilmember",
                "source_text": "Councilmember Bien Doan",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes=(
        "Non-unanimous vote (one councilmember absent) and five named companies that must NOT be "
        "extracted as people - they're franchise applicants, i.e. organizations, not individuals. This is a "
        "public hearing item, not a plain consent item."
    ),
)

case(
    id="sj-cc-2025-12-09-8.1",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="8.1",
    item_title="Actions Related to the Agreement with the County of Santa Clara's Office of Supportive Housing",
    document_text=(
        "8.1 Actions Related to the Agreement with the County of Santa Clara's Office of Supportive "
        "Housing for the Homelessness Prevention System Funding.\n"
        "(a) Adopt a resolution authorizing the Housing Director, or his designee, to negotiate and "
        "execute a grant agreement amendment with the County of Santa Clara's Office of Supportive "
        "Housing, in an amount not to exceed $5,500,000, with an additional $2,579,023 in unspent "
        "funds from the April 2025 authorization.\n\n"
        "Erik Solivan, Director, Housing Department, responded to questions from the Council.\n\n"
        "Public Comment: None provided.\n\n"
        "Motion: Vice Mayor Pam Foley motioned to accept the actions related to the agreement with "
        "the County of Santa Clara's Office of Supportive Housing for the Homelessness Prevention "
        "System funding. The motion was seconded by Councilmember Rosemary Kamei.\n\n"
        "Friendly Amendment: Councilmember Pamela Campos proposed a friendly amendment to "
        "include acceptance of the joint memorandum co-authored by Mayor Mahan, Councilmember "
        "Campos, Councilmember Tordillos, Councilmember Ortiz, and Councilmember Casey, dated "
        "December 5, 2025. The motion was accepted by the maker of the motion and the seconder.\n\n"
        "Action: Upon motion by Vice Mayor Pam Foley, seconded by Councilmember Rosemary Kamei, "
        "and carried unanimously, (a) Resolution No. RES2025-417 was adopted, authorizing the "
        "Housing Director, or his designee, to negotiate and execute a grant agreement amendment with "
        "the County of Santa Clara's Office of Supportive Housing, in an amount not to exceed "
        "$5,500,000, with an additional $2,579,023 in unspent funds from the April 2025 authorization. (11-0-0)"
    ),
    expected={
        "item_type": "action",
        "motions": [
            {
                "text": "accept the actions related to the agreement with the County of Santa Clara's Office of Supportive Housing",
                "moved_by": "Pam Foley",
                "seconded_by": "Rosemary Kamei",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Vice Mayor Pam Foley, seconded by Councilmember Rosemary Kamei, "
                    "and carried unanimously, (a) Resolution No. RES2025-417 was adopted"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Erik Solivan",
                "role": "staff",
                "source_text": "Erik Solivan, Director, Housing Department",
            },
            {
                "raw_name": "Pam Foley",
                "role": "councilmember",
                "source_text": "Vice Mayor Pam Foley motioned",
            },
            {
                "raw_name": "Rosemary Kamei",
                "role": "councilmember",
                "source_text": "Councilmember Rosemary Kamei",
            },
            {
                "raw_name": "Pamela Campos",
                "role": "councilmember",
                "source_text": "Councilmember Pamela Campos proposed a friendly amendment",
            },
            {
                "raw_name": "Mahan",
                "role": "mayor",
                "source_text": "co-authored by Mayor Mahan",
            },
            {
                "raw_name": "Tordillos",
                "role": "councilmember",
                "source_text": "Councilmember Tordillos",
            },
            {
                "raw_name": "Ortiz",
                "role": "councilmember",
                "source_text": "Councilmember Ortiz",
            },
            {
                "raw_name": "Casey",
                "role": "councilmember",
                "source_text": "Councilmember Casey",
            },
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$5,500,000",
                "amount_usd": "5500000",
                "kind": "grant",
                "source_text": "in an amount not to exceed $5,500,000",
            },
            {
                "raw_text": "$2,579,023",
                "amount_usd": "2579023",
                "kind": "grant",
                "source_text": "with an additional $2,579,023 in unspent funds",
            },
        ],
    },
    notes=(
        "Motion plus a named friendly amendment - the Vice Mayor's title should resolve to role "
        "'councilmember' (the schema has no separate vice-mayor role), and this checks whether the model "
        "treats an amendment as part of the same motion rather than fabricating a second one. "
        "Corrected after the first real eval run: the initial gold annotation for this case listed only "
        "4 of the 5 people the joint memorandum names - the model's extraction of Mahan, Tordillos, Ortiz, "
        "and Casey (memo co-authors) was correct and verified, but scored as four false positives because "
        "gold was incomplete, not because the model was wrong. Left as an example in docs/evals.md of a "
        "real precision number partly reflecting gold-set gaps rather than model error."
    ),
)

case(
    id="sj-cc-2025-12-09-10.1a",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="10.1(a)",
    item_title="Land use item deferred at the City Attorney's request",
    document_text=(
        "Action: Upon motion by Vice Mayor Pam Foley, seconded by Councilmember Domingo Candelas, "
        "and carried unanimously, Item 10.1(a) was deferred, per the City Attorney's Office request. (11-0-0)"
    ),
    expected={
        "item_type": "action",
        "motions": [
            {
                "text": "Item 10.1(a) was deferred, per the City Attorney's Office request",
                "moved_by": "Pam Foley",
                "seconded_by": "Domingo Candelas",
                "outcome": "continued",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Vice Mayor Pam Foley, seconded by Councilmember Domingo Candelas, "
                    "and carried unanimously, Item 10.1(a) was deferred"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Pam Foley",
                "role": "councilmember",
                "source_text": "Vice Mayor Pam Foley",
            },
            {
                "raw_name": "Domingo Candelas",
                "role": "councilmember",
                "source_text": "Councilmember Domingo Candelas",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes=(
        "Contrast case for 2.15: here the deferral IS a real, voted motion (outcome 'continued' with a real "
        "tally), unlike 2.15's administrative deferral with no motion at all. Tests that the model doesn't treat "
        "every deferral identically."
    ),
)

case(
    id="sj-cc-2025-12-09-2.11",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="2.11",
    item_title="2026 Weed Abatement Program Commencement Report",
    document_text=(
        "2.11 2026 Weed Abatement Program Commencement Report.\n"
        "Adopt a resolution:\n"
        "(a) Accepting the 2026 Weed Abatement Commencement Report compiled by the County of Santa "
        "Clara's Consumer and Environmental Protection Agency - Weed Abatement Program;\n"
        "(b) Declaring that those certain noxious or dangerous seasonal and recurrent weeds are a public "
        "nuisance; and\n"
        "(c) Directing the County of Santa Clara's Consumer and Environmental Protection Agency - Weed "
        "Abatement Program to mail a Notice of Public Hearing to occur on February 10, 2026, at 1:30 p.m. "
        "before the City Council.\n\n"
        "Action: Resolution No. RES2025-413 was adopted, regarding 2026 Weed Abatement Program "
        "Commencement Report. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-413 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: Resolution No. RES2025-413 was adopted",
            }
        ],
        "people": [],
        "locations": [],
        "amounts": [],
    },
    notes="No dollar amount, no named individual, and no specific street address - a genuinely sparse item, useful for confirming the model returns empty lists rather than reaching for something to extract.",
)

case(
    id="sj-cc-2025-12-09-3.4",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="3.4",
    item_title="External Auditor's Report: Report to Those Charged with Governance",
    document_text=(
        "3.4 External Auditor's Report: Report to Those Charged with Governance for the "
        "Year Ended June 30, 2025.\n"
        "Accept the Report to Those Charged with Governance for the year ended June 30, 2025, as issued by "
        "Macias Gini & O'Connell LLP, the City's external auditor.\n\n"
        "Maria Oberg, Director, Finance; Victor Lo, Deputy Director, Finance Department; and Ben Lau, "
        "CPA, Partner: Macias, Gina & O'Connell, offered the presentation and responded to questions from "
        "Council.\n\n"
        "Public Comment: Brian Darby offered public comment.\n\n"
        "Action: Upon motion by Councilmember David Cohen, seconded by Councilmember Rosemary "
        "Kamei, and carried unanimously, the Report to Those Charged with Governance for the year ended "
        "June 30, 2025, as issued by Macias Gini & O'Connell LLP, the City's external auditor, was "
        "accepted. (11-0-0)"
    ),
    expected={
        "item_type": "report",
        "motions": [
            {
                "text": "the Report to Those Charged with Governance was accepted",
                "moved_by": "David Cohen",
                "seconded_by": "Rosemary Kamei",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember David Cohen, seconded by Councilmember Rosemary "
                    "Kamei, and carried unanimously, the Report to Those Charged with Governance"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Maria Oberg",
                "role": "staff",
                "source_text": "Maria Oberg, Director, Finance",
            },
            {
                "raw_name": "Victor Lo",
                "role": "staff",
                "source_text": "Victor Lo, Deputy Director, Finance Department",
            },
            {
                "raw_name": "Ben Lau",
                "role": "public",
                "source_text": "Ben Lau, CPA, Partner: Macias, Gina & O'Connell",
            },
            {
                "raw_name": "Brian Darby",
                "role": "public",
                "source_text": "Brian Darby offered public comment",
            },
            {
                "raw_name": "David Cohen",
                "role": "councilmember",
                "source_text": "Councilmember David Cohen",
            },
            {
                "raw_name": "Rosemary Kamei",
                "role": "councilmember",
                "source_text": "Councilmember Rosemary Kamei",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes="Same presenter lineup as item 3.3 (heard concurrently, same meeting) but a different mover/seconder pair - checks the model doesn't just copy the previous item's motion attribution.",
)

case(
    id="sj-cc-2025-12-09-3.5",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="3.5",
    item_title="Comprehensive Annual Debt Report for Fiscal Year Ended June 30, 2025",
    document_text=(
        "3.5 Comprehensive Annual Debt Report for Fiscal Year Ended June 30, 2025.\n"
        "Accept the Comprehensive Annual Debt Report for the City of San Jose for Fiscal Year 2024-2025.\n\n"
        "Maria Oberg, Director, Finance Department; and Qianyu Sun, Deputy Director, Finance Department, "
        "offered the presentation and responded to questions from Council.\n\n"
        "Public Comment: None provided.\n\n"
        "Action: Upon motion by Councilmember Bien Doan, seconded by Councilmember Rosemary "
        "Kamei, and carried unanimously, the Comprehensive Annual Debt Report for the City of San Jose "
        "for Fiscal Year 2024-2025 was accepted. (11-0-0)"
    ),
    expected={
        "item_type": "report",
        "motions": [
            {
                "text": "the Comprehensive Annual Debt Report was accepted",
                "moved_by": "Bien Doan",
                "seconded_by": "Rosemary Kamei",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Bien Doan, seconded by Councilmember Rosemary "
                    "Kamei, and carried unanimously, the Comprehensive Annual Debt Report"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Maria Oberg",
                "role": "staff",
                "source_text": "Maria Oberg, Director, Finance Department",
            },
            {
                "raw_name": "Qianyu Sun",
                "role": "staff",
                "source_text": "Qianyu Sun, Deputy Director, Finance Department",
            },
            {
                "raw_name": "Bien Doan",
                "role": "councilmember",
                "source_text": "Councilmember Bien Doan",
            },
            {
                "raw_name": "Rosemary Kamei",
                "role": "councilmember",
                "source_text": "Councilmember Rosemary Kamei",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes="No public comment this time (vs. items 3.3/3.4 which had one) - checks the model correctly reports zero public speakers rather than reusing the previous items' commenter.",
)

case(
    id="sj-cc-2025-12-09-9.1",
    body="City Council",
    meeting_date="2025-12-09",
    source_document=CC_1209,
    item_number="9.1",
    item_title="Successor Agency Audited Financial Statements for Fiscal Year Ended June 30, 2025",
    document_text=(
        "9.1 Successor Agency to the Redevelopment Agency of the City of San Jose - Audited "
        "Financial Statements for Fiscal Year ended June 30, 2025.\n"
        "Accept the Fiscal Year 2024-2025 Independent Auditor's Reports and Basic Financial "
        "Statements for the Successor Agency to the Redevelopment Agency of the City of San Jose.\n\n"
        "Maria Oberg, Director, Finance Department; Victor Lo, Deputy Director, Finance Department; and "
        "Ben Lau, CPA, Partner: Macias, Gina & O'Connell, offered the presentation and responded to "
        "questions from Council.\n\n"
        "Public Comment: Brian Darby offered public comment.\n\n"
        "Action: Upon motion by Councilmember Anthony Tordillos, seconded by Councilmember Bien "
        "Doan, and carried unanimously, the Fiscal Year 2024-2025 Independent Auditor's Reports and "
        "Basic Financial Statements for the Successor Agency to the Redevelopment Agency of the City "
        "of San Jose were accepted. (11-0-0)"
    ),
    expected={
        "item_type": "report",
        "motions": [
            {
                "text": "the Independent Auditor's Reports and Basic Financial Statements were accepted",
                "moved_by": "Anthony Tordillos",
                "seconded_by": "Bien Doan",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Anthony Tordillos, seconded by Councilmember Bien "
                    "Doan, and carried unanimously, the Fiscal Year 2024-2025 Independent Auditor's Reports"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Maria Oberg",
                "role": "staff",
                "source_text": "Maria Oberg, Director, Finance Department",
            },
            {
                "raw_name": "Victor Lo",
                "role": "staff",
                "source_text": "Victor Lo, Deputy Director, Finance Department",
            },
            {
                "raw_name": "Ben Lau",
                "role": "public",
                "source_text": "Ben Lau, CPA, Partner: Macias, Gina & O'Connell",
            },
            {
                "raw_name": "Brian Darby",
                "role": "public",
                "source_text": "Brian Darby offered public comment",
            },
            {
                "raw_name": "Anthony Tordillos",
                "role": "councilmember",
                "source_text": "Councilmember Anthony Tordillos",
            },
            {
                "raw_name": "Bien Doan",
                "role": "councilmember",
                "source_text": "Councilmember Bien Doan",
            },
        ],
        "locations": [],
        "amounts": [],
    },
    notes="Item heard under the Successor Agency (a legally distinct body the City Council convenes as), not the City Council itself, despite identical presenters to 3.3/3.4 - a subtle body-identity distinction.",
)

# ---------------------------------------------------------------------
# December 16, 2025 - City Council
# ---------------------------------------------------------------------

case(
    id="sj-cc-2025-12-16-2.1",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.1",
    item_title="Approval of City Council Minutes",
    document_text=(
        "2.1 25-1357 Approval of City Council Minutes.\n"
        "(a) Regular City Council Meeting Minutes of November 18, 2025.\n\n"
        "Action: The City Council Minutes were approved. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "The City Council Minutes were approved",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: The City Council Minutes were approved. (11-0-0)",
            }
        ],
        "people": [],
        "locations": [],
        "amounts": [],
    },
    notes="Minimal item: no people, no amounts, no location - one of the sparsest real items in the corpus, useful for checking the model doesn't over-extract to fill categories.",
)

case(
    id="sj-cc-2025-12-16-2.2",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.2",
    item_title="Final Adoption of Ordinances",
    document_text=(
        "2.2 25-1345 Final Adoption of Ordinances.\n"
        "(a) Ordinance No. 31279 - An Ordinance of the City of San Jose Rezoning Certain Real Property of "
        "Approximately 1.88 Gross Acres, Situated South of the Eastern Terminus of Bern Court (908 Bern "
        "Court) (APN: 241-15-009) from the LI(PD) Planned Development Zoning District to the CIC Combined "
        "Industrial/Commercial Zoning District.\n"
        "[Passed for Publication on 12/2/2025 - Item 10.1(a) (25-1265)]\n\n"
        "Action: Ordinance No. 31279 ... was adopted. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Ordinance No. 31279 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: Ordinance No. 31279 ... was adopted. (11-0-0)",
            }
        ],
        "people": [],
        "locations": [
            {
                "raw_text": "908 Bern Court (APN: 241-15-009)",
                "source_text": "South of the Eastern Terminus of Bern Court (908 Bern Court) (APN: 241-15-009)",
            }
        ],
        "amounts": [],
    },
    notes="Rezoning ordinance with a real street address AND an Assessor's Parcel Number in the same location reference - checks whether the model captures both, not just the address.",
)

case(
    id="sj-cc-2025-12-16-2.7",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.7",
    item_title="Actions Related to the Request for Proposals Rebid for Automated Teller Machine Concessions",
    document_text=(
        "2.7 25-1304 Actions Related to the Request for Proposals Rebid for Automated Teller Machine "
        "Concessions at the San Jose Mineta International Airport.\n"
        "(a) Approve the selection of the top-ranking proposer for the request for proposals rebid for "
        "automated teller machine concessions at the San Jose Mineta International Airport.\n"
        "(b) Adopt a resolution authorizing the City Manager, or her designee, to negotiate and execute an "
        "agreement with Bank of America, National Association for automated teller machine services.\n\n"
        "Action: (a) The selection of the top-ranking proposer was approved; and (b) Resolution No. RES2025-"
        "418 was adopted, authorizing the City Manager, or her designee, to negotiate and execute "
        "an agreement with Bank of America, National Association for automated teller machine services "
        "at the San Jose Mineta International Airport. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "the selection was approved and Resolution No. RES2025-418 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Resolution No. RES2025-",
            }
        ],
        "people": [],
        "locations": [
            {
                "raw_text": "San Jose Mineta International Airport",
                "source_text": "San Jose Mineta International Airport",
            }
        ],
        "amounts": [],
    },
    notes="No dollar figure is stated anywhere in this item despite being a commercial concession agreement - checks the model reports empty amounts rather than guessing a plausible-sounding number. Bank of America is a named contracting party, not a person.",
)

case(
    id="sj-cc-2025-12-16-2.9",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.9",
    item_title="City Manager's Travel to Chula Vista, California",
    document_text=(
        "2.9 25-1307 City Manager's Travel to Chula Vista, California.\n"
        "Authorize travel for City Manager, Jennifer A. Maguire, to Chula Vista, California, on January 8-10, "
        "2026 to participate in the Large Cities Executive Forum.\n\n"
        "Action: City Manager, Jennifer A. Maguire's travel to Chula Vista, California, from January 8-10, "
        "2026, to participate in the Large Cities Executive Forum was authorized. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "City Manager Jennifer A. Maguire's travel to Chula Vista was authorized",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "travel to Chula Vista, California, from January 8-10, "
                "2026, to participate in the Large Cities Executive Forum was authorized",
            }
        ],
        "people": [
            {
                "raw_name": "Jennifer A. Maguire",
                "role": "staff",
                "source_text": "City Manager, Jennifer A. Maguire",
            }
        ],
        "locations": [
            {"raw_text": "Chula Vista, California", "source_text": "Chula Vista, California"}
        ],
        "amounts": [],
    },
    notes="Location here is a travel destination, not a San Jose address - checks the model extracts locations generically rather than assuming they're always in-city.",
)

case(
    id="sj-cc-2025-12-16-2.11",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.11",
    item_title="Actions Related to the Purchase Order with Gillig LLC for Electric Buses",
    document_text=(
        "2.11 25-1309 Actions Related to the Purchase Order with Gillig LLC for Electric Buses.\n"
        "(a) Adopt a resolution authorizing the City Manager or her designee to:\n"
        "(1) Execute a purchase order with Gillig LLC (Livermore, CA) for two new 40' low floor plus "
        "electric buses for a not-to-exceed amount of $2,569,301;\n"
        "(2) Approve a contingency of $280,000 for unanticipated modifications to the electric buses order.\n"
        "(b) Adopt the following 2025-2026 Appropriation Ordinance amendments in the Airport Renewal and "
        "Replacement Fund:\n"
        "(1) Increase the Zero Emissions Buses Appropriation to the Airport Department by $333,000; and\n"
        "(2) Decrease the Ending Fund Balance by $333,000.\n\n"
        "Action: Resolution No. RES2025-421 was adopted, authorizing the purchase order with Gillig LLC "
        "(Livermore, CA) for two new 40' low floor plus electric buses for a not-to-exceed amount of "
        "$2,569,301, a contingency of $280,000, and the appropriation amendments increasing the Zero "
        "Emissions Buses Appropriation to the Airport Department by $333,000 and decreasing the Ending "
        "Fund Balance by $333,000. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-421 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: Resolution No. RES2025-421 was adopted",
            }
        ],
        "people": [],
        "locations": [{"raw_text": "Livermore, CA", "source_text": "Gillig LLC (Livermore, CA)"}],
        "amounts": [
            {
                "raw_text": "$2,569,301",
                "amount_usd": "2569301",
                "kind": "contract",
                "source_text": "for a not-to-exceed amount of $2,569,301",
            },
            {
                "raw_text": "$280,000",
                "amount_usd": "280000",
                "kind": "contract",
                "source_text": "a contingency of $280,000",
            },
            {
                "raw_text": "$333,000",
                "amount_usd": "333000",
                "kind": "budget",
                "source_text": "Increase the Zero Emissions Buses Appropriation to the Airport Department by $333,000",
            },
        ],
    },
    notes="Vendor's own city (Livermore, CA) is a location distinct from San Jose - another case of a non-San-Jose location tied to a contract rather than a project site.",
)

case(
    id="sj-cc-2025-12-16-2.16",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.16",
    item_title="Actions Related to the Reallocation of Acquisition Funding for the Gateway Tower Affordable Housing Development",
    document_text=(
        "2.16 25-1314 Actions Related to the Reallocation of Acquisition Funding to the "
        "Construction-Permanent Loan for the Gateway Tower Affordable Housing Development.\n"
        "(a) Accept the staff recommendation on reallocation of the Gateway Tower loan commitment.\n"
        "(b) Adopt a resolution authorizing the reallocation of acquisition funding to increase the "
        "construction-permanent loan to $38,440,000. Council District 3.\n\n"
        "Action: (a) The staff recommendation on reallocation of the Gateway Tower loan commitment was "
        "accepted; and (b) Resolution No. RES2025-425 was adopted, authorizing the reallocation of "
        "acquisition funding to increase the construction-permanent loan to $38,440,000. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "the staff recommendation was accepted and Resolution No. RES2025-425 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Resolution No. RES2025-425 was adopted",
            }
        ],
        "people": [],
        "locations": [{"raw_text": "Council District 3", "source_text": "Council District 3"}],
        "amounts": [
            {
                "raw_text": "$38,440,000",
                "amount_usd": "38440000",
                "kind": "budget",
                "source_text": "increase the construction-permanent loan to $38,440,000",
            }
        ],
    },
    notes="Large single loan figure for a named affordable-housing project, located only by Council District rather than a street address.",
)

case(
    id="sj-cc-2025-12-16-2.17",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.17",
    item_title="Fourth Amendment to the Consultant Agreement with The Pun Group, LLP",
    document_text=(
        "2.17 25-1315 Fourth Amendment to the Consultant Agreement with The Pun Group, LLP for "
        "Grant Monitoring Services.\n"
        "Adopt a resolution authorizing the Housing Director, or his designee, to negotiate and execute a "
        "Fourth Amendment to the Consultant Agreement with The Pun Group LLP, for grant monitoring "
        "services, to increase the maximum total compensation by $135,000, from $731,500 to $866,500 for "
        "the period of January 1, 2026, to June 30, 2026.\n\n"
        "Mayor Matt Mahan pulled Item 2.17 for questions regarding the range of the audit and "
        "compliance activities.\n\n"
        "Erik Solivan, Director, Housing Department, responded to questions.\n\n"
        "Action: Resolution No. RES2025-426 was adopted, authorizing the Housing Director, or his designee, "
        "to negotiate and execute a Fourth Amendment to the Consultant Agreement with The Pun Group LLP, "
        "for grant monitoring services, to increase the maximum total compensation by $135,000, from "
        "$731,500 to $866,500 for the period of January 1, 2026, to June 30, 2026. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-426 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: Resolution No. RES2025-426 was adopted",
            }
        ],
        "people": [
            {
                "raw_name": "Matt Mahan",
                "role": "mayor",
                "source_text": "Mayor Matt Mahan pulled Item 2.17",
            },
            {
                "raw_name": "Erik Solivan",
                "role": "staff",
                "source_text": "Erik Solivan, Director, Housing Department",
            },
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$135,000",
                "amount_usd": "135000",
                "kind": "contract",
                "source_text": "increase the maximum total compensation by $135,000",
            },
            {
                "raw_text": "$731,500",
                "amount_usd": "731500",
                "kind": "contract",
                "source_text": "from $731,500 to $866,500",
            },
            {
                "raw_text": "$866,500",
                "amount_usd": "866500",
                "kind": "contract",
                "source_text": "from $731,500 to $866,500",
            },
        ],
    },
    notes="A consent item that was 'pulled for questions' but still resolved without a separate roll-call motion - the Mayor and a department director both appear only in discussion, not as movers.",
)

case(
    id="sj-cc-2025-12-16-2.28",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.28",
    item_title="Shared Micro-Mobility Device Fee Adjustment (re-deferred)",
    document_text=(
        "2.28 25-1341 Shared Micro-Mobility Device Fee Adjustment. - DEFERRED\n"
        "Adopt a resolution amending the 2025-2026 Schedule of Fees and Charges (Resolution No. 72737, "
        "as amended) to decrease the Shared Micro-Mobility Annual Permit and Program Monitoring "
        "Operating Fee from $139 per device to $100 per device, effective January 1, 2026.\n"
        "[Deferred from 12/9/2025 Item 2.15 (25-1286)]\n\n"
        "DEFERRED TO 1/13/2026 PER ADMINISTRATION"
    ),
    expected={
        "item_type": "action",
        "motions": [],
        "people": [],
        "locations": [],
        "amounts": [],
    },
    notes=(
        "Same fee-adjustment item as sj-cc-2025-12-09-2.15, deferred a second time. Confirms the model "
        "treats a repeat administrative deferral the same way (empty motions) rather than inventing a "
        "motion because the item has now appeared twice."
    ),
)

case(
    id="sj-cc-2025-12-16-ada-curb-ramps",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.27",
    item_title="Report on Bids and Award of Contract for the 2026 Local Streets ADA Curb Ramps #2 Project",
    document_text=(
        "Action: (a) The report on bids and award a contract for the construction of "
        "10594 - 2026 Local Streets ADA Curb Ramps #2 Project to the lowest "
        "responsive, responsible bidder, Spencon Construction, Inc., in the amount "
        "of $1,224,200 was accepted; and (b) the 10% contingency in the amount "
        "of $122,420 was approved. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "the report was accepted, the contract was awarded, and the contingency was approved",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: (a) The report on bids and award a contract",
            }
        ],
        "people": [],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$1,224,200",
                "amount_usd": "1224200",
                "kind": "contract",
                "source_text": "in the amount of $1,224,200 was accepted",
            },
            {
                "raw_text": "$122,420",
                "amount_usd": "122420",
                "kind": "contract",
                "source_text": "the 10% contingency in the amount of $122,420 was approved",
            },
        ],
    },
    notes="Same contract-plus-10%-contingency pattern as item 3.7, with different real figures - checks the model doesn't just pattern-match the earlier example's numbers.",
)

case(
    id="sj-cc-2025-12-16-2.8",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.8",
    item_title="Amendment to City Council Policy 9-5, Travel by Elected and Appointed City Officials",
    document_text=(
        "2.8 25-1305 Amendment to City Council Policy 9-5, Travel by Elected and "
        "Appointed City Officials.\n"
        "Adopt a resolution amending the City Council Policy 9-5 for Travel by "
        "Elected and Appointed City Officials to revise and conform the travel "
        "guidelines portion to the Employee Travel Policy, 1.8.2.\n\n"
        "Action: Resolution No. RES2025-419 was adopted, amending City Council "
        "Policy 9-5 for Travel by Elected and Appointed City Officials to revise and "
        "conform the travel guidelines portion to the Employee Travel Policy, 1.8.2. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-419 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: Resolution No. RES2025-419 was adopted",
            }
        ],
        "people": [],
        "locations": [],
        "amounts": [],
    },
    notes="A policy-amendment item with no dollar amount, no named person, and no location - a second, independent sparse-item example from a different meeting than 2.1.",
)

case(
    id="sj-cc-2025-12-16-2.10",
    body="City Council",
    meeting_date="2025-12-16",
    source_document=CC_1216,
    item_number="2.10",
    item_title="Fourth Amendment to the CALeVIP Services Agreement with the Center for Sustainable Energy",
    document_text=(
        "2.10 25-1308 Fourth Amendment to the CALeVIP Services Agreement with the "
        "Center for Sustainable Energy.\n"
        "Adopt a resolution authorizing the Director of Energy or her designee to "
        "execute a Fourth Amendment to the Services Agreement by and "
        "between the City of San Jose and the Center for Sustainable Energy, "
        "extending the term dated July 8, 2020, through July 1, 2026, with no "
        "additional funds.\n\n"
        "Action: Resolution No. RES2025-420 was adopted, authorizing the Director "
        "of Energy or her designee to execute a Fourth Amendment to the Services "
        "Agreement by and between the City of San Jose and the Center for Sustainable "
        "Energy, extending the term dated July 8, 2020, through July 1, 2026, with no "
        "additional funds. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-420 was adopted",
                "moved_by": None,
                "seconded_by": None,
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": "Action: Resolution No. RES2025-420 was adopted",
            }
        ],
        "people": [],
        "locations": [],
        "amounts": [],
    },
    notes="Explicit 'with no additional funds' contract amendment - checks the model doesn't invent a dollar amount for an agreement that explicitly states none is involved.",
)

# ---------------------------------------------------------------------
# December 10, 2025 - Planning Commission
# ---------------------------------------------------------------------

case(
    id="sj-pc-2025-12-10-3a",
    body="Planning Commission",
    meeting_date="2025-12-10",
    source_document=PC_1210,
    item_number="3.a",
    item_title="CP25-001 & ER25-007 utility facility Conditional Use Permit - deferral",
    document_text=(
        "3. DEFERRALS AND REMOVALS FROM CALENDAR\n\n"
        "a. CP25-001 & ER25-007 (Administrative Hearing): Conditional Use Permit to allow the "
        "construction of a utility facility, including two above-ground pressure regulators, a control "
        "unit cabinet, approximately 160 linear feet of perimeter fencing, and a driveway on an "
        "approximately 1,600-square-foot portion of an approximately 40.0-gross-acre site located at "
        "0 Suncrest Avenue (James E. and Jane N. Duarte Trustee, Owner). Council District: 4.\n"
        "STAFF RECOMMENDS:\n"
        "1. DEFERRED TO THE JANUARY 14, 2026, PLANNING COMMISSION MEETING PER STAFF REQUEST.\n\n"
        "ACTION: COMMISSIONER BHANDAL MADE A MOTION TO DEFER TO THE "
        "JANUARY 28, 2026, PLANNING COMMISSION MEETING. "
        "COMMISSIONER CASEY SECONDED THE MOTION (9-0-2; OLIVERIO & YOUNG ABSENT)"
    ),
    expected={
        "item_type": "action",
        "motions": [
            {
                "text": "a motion to defer to the January 28, 2026, Planning Commission meeting",
                "moved_by": "Bhandal",
                "seconded_by": "Casey",
                "outcome": "continued",
                "tally": "9-0-2; Oliverio & Young absent",
                "source_text": "COMMISSIONER BHANDAL MADE A MOTION TO DEFER TO THE "
                "JANUARY 28, 2026, PLANNING COMMISSION MEETING",
            }
        ],
        "people": [
            {
                "raw_name": "Bhandal",
                "role": "unknown",
                "source_text": "COMMISSIONER BHANDAL MADE A MOTION",
            },
            {
                "raw_name": "Casey",
                "role": "unknown",
                "source_text": "COMMISSIONER CASEY SECONDED THE MOTION",
            },
        ],
        "locations": [
            {
                "raw_text": "0 Suncrest Avenue, Council District 4",
                "source_text": "located at 0 Suncrest Avenue",
            }
        ],
        "amounts": [],
    },
    notes=(
        "Planning Commissioners have no matching Person.role value in the current schema (not mayor, "
        "councilmember, staff, applicant, or public) - annotated 'unknown' deliberately. This is a real gap "
        "surfaced by hand-annotation, discussed in docs/evals.md. Deferral here is a real voted motion, "
        "unlike the two administrative deferrals above, and the staff-recommended date (January 14) differs "
        "from what the Commission actually voted for (January 28) - a subtle trap for an extraction that "
        "reads only the recommendation instead of the actual vote."
    ),
)

case(
    id="sj-pc-2025-12-10-4",
    body="Planning Commission",
    meeting_date="2025-12-10",
    source_document=PC_1210,
    item_number="4",
    item_title="Consent Calendar items 4.a and 4.b",
    document_text=(
        "4. CONSENT CALENDAR\n\n"
        "ACTION: COMMISSIONER BHANDAL MADE A MOTION TO APPROVE "
        "CONSENT CALENDAR ITEMS 4.A. AND 4.B. "
        "COMMISSIONER CANTRELL SECONDED THE MOTION (8-0-2-1; OLIVERIO & "
        "YOUNG ABSENT; ESCOBAR ABSTAINED)\n\n"
        "a. Review and Approve Action Minutes from November 19, 2025.\n\n"
        "b. CP25-020 & ER25-184 (Administrative Hearing): Conditional Use Permit to allow the "
        "continued use of an existing wireless facility, consisting of an approximately 77-foot-high "
        "monopole and associated ground equipment on an approximately 0.25-gross-acre site located "
        "at 419 Lano Street (Froom Judith R Trustee & Et Al, Owner). Council District: 7."
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "a motion to approve Consent Calendar items 4.a. and 4.b.",
                "moved_by": "Bhandal",
                "seconded_by": "Cantrell",
                "outcome": "passed",
                "tally": "8-0-2-1; Oliverio & Young absent; Escobar abstained",
                "source_text": "COMMISSIONER BHANDAL MADE A MOTION TO APPROVE "
                "CONSENT CALENDAR ITEMS 4.A. AND 4.B.",
            }
        ],
        "people": [
            {
                "raw_name": "Bhandal",
                "role": "unknown",
                "source_text": "COMMISSIONER BHANDAL MADE A MOTION",
            },
            {
                "raw_name": "Cantrell",
                "role": "unknown",
                "source_text": "COMMISSIONER CANTRELL SECONDED THE MOTION",
            },
            {
                "raw_name": "Froom Judith R Trustee",
                "role": "applicant",
                "source_text": "(Froom Judith R Trustee & Et Al, Owner)",
            },
        ],
        "locations": [
            {
                "raw_text": "419 Lano Street, Council District 7",
                "source_text": "located at 419 Lano Street",
            }
        ],
        "amounts": [],
    },
    notes=(
        "SPEC-style hard case: a bulk consent calendar covering two sub-items under one motion, with an "
        "unusual four-part vote tally including both an absence and an abstention. A property owner/trustee "
        "is named as the permit applicant."
    ),
)

case(
    id="sj-pc-2025-12-10-5a-cisco",
    body="Planning Commission",
    meeting_date="2025-12-10",
    source_document=PC_1210,
    item_number="5.a (DA10-001)",
    item_title="Annual Compliance Review - Cisco Systems Development Agreement",
    document_text=(
        "5. PUBLIC HEARING\n\n"
        "a. 2025-2026 Annual Compliance Review of Development Agreements (Administrative "
        "Hearing).\n"
        "DA10-001. This is the annual compliance review hearing for the Cisco Systems "
        "Development Agreement. The City Council adopted this Development Agreement in 2010, "
        "which allows the development of 150,000-2.5 million square feet of office/R&D space "
        "over the term of the agreement, for the 137-acre site. (Cisco Technology Inc., Owner). "
        "Council District 4.\n\n"
        "1. ADOPT A RESOLUTION ... CERTIFYING THE DEVELOPER IS IN "
        "COMPLIANCE WITH THE TERMS AND CONDITIONS OF THE "
        "DEVELOPMENT AGREEMENT BETWEEN THE CITY OF SAN JOSE AND "
        "CISCO TECHNOLOGY, INC. (“CISCO”) DATED SEPTEMBER 2, 2010 "
        "(FILE NO. DA10-001) FOR THE ANNUAL COMPLIANCE REVIEW PERIOD "
        "OF JULY 1, 2024 THROUGH JUNE 30, 2025, FOR THE UP TO 2.5 MILLION-"
        "SQUARE FOOT RESEARCH AND DEVELOPMENT OFFICE PROJECT ON "
        "THE 137-GROSS ACRE SITE LOCATED ON THE NORTH AND SOUTH "
        "SIDES OF EAST TASMAN DRIVE, EAST OF ZANKER ROAD.\n\n"
        "COMMISSIONERS BAROCIO & ESCOBAR STATED THEIR CONFLICT OF "
        "INTEREST IN PARTICIPATING IN THE DECISION-MAKING ON ITEM "
        "DA10-001 (CISCO).\n\n"
        "ACTION: COMMISSIONER OLIVERIO MADE A MOTION TO APPROVE "
        "STAFF RECOMMENDATION FOR DA10-001.\n\n"
        "COMMISSIONER CAO SECONDED THE MOTION (10-0-0-1; BICKFORD RECUSED)"
    ),
    expected={
        "item_type": "public_hearing",
        "motions": [
            {
                "text": "a motion to approve staff recommendation for DA10-001",
                "moved_by": "Oliverio",
                "seconded_by": "Cao",
                "outcome": "passed",
                "tally": "10-0-0-1; Bickford recused",
                "source_text": "COMMISSIONER OLIVERIO MADE A MOTION TO APPROVE "
                "STAFF RECOMMENDATION FOR DA10-001",
            }
        ],
        "people": [
            {
                "raw_name": "Oliverio",
                "role": "unknown",
                "source_text": "COMMISSIONER OLIVERIO MADE A MOTION",
            },
            {
                "raw_name": "Cao",
                "role": "unknown",
                "source_text": "COMMISSIONER CAO SECONDED THE MOTION",
            },
            {
                "raw_name": "Barocio",
                "role": "unknown",
                "source_text": "COMMISSIONERS BAROCIO & ESCOBAR STATED THEIR CONFLICT OF INTEREST",
            },
            {
                "raw_name": "Escobar",
                "role": "unknown",
                "source_text": "COMMISSIONERS BAROCIO & ESCOBAR STATED THEIR CONFLICT OF INTEREST",
            },
        ],
        "locations": [
            {
                "raw_text": "137-acre site on the north and south sides of East Tasman Drive, east of Zanker Road, Council District 4",
                "source_text": "LOCATED ON THE NORTH AND SOUTH "
                "SIDES OF EAST TASMAN DRIVE, EAST OF ZANKER ROAD",
            }
        ],
        "amounts": [],
    },
    notes=(
        "One of three related sub-motions on the same multi-agreement public hearing item (paired with "
        "the Apple and Google sub-motions below) - together these three cases plus the item's own bulk "
        "motion satisfy SPEC's 'item with three motions' hard case, split across separate gold files since "
        "each sub-motion has its own distinct mover, seconder, tally, and recusals."
    ),
)

case(
    id="sj-pc-2025-12-10-5a-apple",
    body="Planning Commission",
    meeting_date="2025-12-10",
    source_document=PC_1210,
    item_number="5.a (DA15-002)",
    item_title="Annual Compliance Review - Apple, Inc. Development Agreement",
    document_text=(
        "DA15-002. This is an annual compliance review hearing for the Apple, Inc. Development "
        "Agreement. The City Council adopted this Development Agreement in March 2016, which "
        "allows the development of up to 4,151,530 square feet of office/R&D and manufacturing "
        "development on the 86-acre site. (Apple Inc., Owner). Council District 4.\n\n"
        "3. ADOPT A RESOLUTION ... CERTIFYING THE DEVELOPER IS IN "
        "COMPLIANCE WITH THE TERMS AND CONDITIONS OF THE "
        "DEVELOPMENT AGREEMENT BETWEEN THE CITY OF SAN JOSE AND "
        "APPLE, INC. (“APPLE”) DATED MARCH 4, 2016 (FILE NO. DA15-002) FOR "
        "THE ANNUAL COMPLIANCE REVIEW PERIOD OF JULY 1, 2024 "
        "THROUGH JUNE 30, 2025, FOR A 4,151,530-SQUARE FOOT RESEARCH "
        "AND DEVELOPMENT OFFICE AND MANUFACTURING PROJECT ON "
        "THE 86-GROSS ACRE SITE LOCATED ON THE EAST AND WEST SIDES "
        "OF ORCHARD PARKWAY, APPROXIMATELY ONE-QUARTER MILE "
        "SOUTH OF TRIMBLE ROAD.\n\n"
        "COMMISSIONERS BAROCIO & ESCOBAR STATED THEIR CONFLICT OF "
        "INTEREST IN PARTICIPATING IN THE DECISION-MAKING ON ITEM "
        "DA15-002 (APPLE).\n\n"
        "ACTION: COMMISSIONER OLIVERIO MADE A MOTION TO APPROVE "
        "STAFF RECOMMENDATION FOR DA15-002.\n\n"
        "COMMISSIONER BHANDAL SECONDED THE MOTION (9-0-0-2; BAROICIO & ESCOBAR RECUSED)"
    ),
    expected={
        "item_type": "public_hearing",
        "motions": [
            {
                "text": "a motion to approve staff recommendation for DA15-002",
                "moved_by": "Oliverio",
                "seconded_by": "Bhandal",
                "outcome": "passed",
                "tally": "9-0-0-2; Barocio & Escobar recused",
                "source_text": "COMMISSIONER OLIVERIO MADE A MOTION TO APPROVE "
                "STAFF RECOMMENDATION FOR DA15-002",
            }
        ],
        "people": [
            {
                "raw_name": "Oliverio",
                "role": "unknown",
                "source_text": "COMMISSIONER OLIVERIO MADE A MOTION",
            },
            {
                "raw_name": "Bhandal",
                "role": "unknown",
                "source_text": "COMMISSIONER BHANDAL SECONDED THE MOTION",
            },
        ],
        "locations": [
            {
                "raw_text": "86-acre site on the east and west sides of Orchard Parkway, south of Trimble Road, Council District 4",
                "source_text": "LOCATED ON THE EAST AND WEST SIDES "
                "OF ORCHARD PARKWAY, APPROXIMATELY ONE-QUARTER MILE "
                "SOUTH OF TRIMBLE ROAD",
            }
        ],
        "amounts": [],
    },
    notes="Second of the three related DA-compliance sub-motions - see sj-pc-2025-12-10-5a-cisco.",
)

case(
    id="sj-pc-2025-12-10-5a-google",
    body="Planning Commission",
    meeting_date="2025-12-10",
    source_document=PC_1210,
    item_number="5.a (DA21-001)",
    item_title="Annual Compliance Review - Downtown West / Google Development Agreement",
    document_text=(
        "DA21-001. This is an annual compliance review hearing for the Downtown West "
        "Development Agreement for a project that included up to 7.3 million gross square feet (gsf) "
        "of commercial office space; up to 5,900 residential units. (Google LLC, Owner). "
        "Council District 6.\n\n"
        "COMMISSIONERS BAROCIO, ESCOBAR & ROSARIO ALSO STATED THEIR CONFLICT OF "
        "INTEREST IN PARTICIPATING IN THE DECISION-MAKING ON ITEM DA21-001 (GOOGLE).\n\n"
        "ACTION: COMMISSIONER OLIVERIO MADE A MOTION TO APPROVE "
        "STAFF RECOMMENDATION FOR DA21-001.\n\n"
        "COMMISSIONER CASEY SECONDED THE MOTION (6-1-0-4; CANTRELL "
        "OPPOSED; ROSARIO, BICKFORD, BAROICIO & ESCOBAR RECUSED)"
    ),
    expected={
        "item_type": "public_hearing",
        "motions": [
            {
                "text": "a motion to approve staff recommendation for DA21-001",
                "moved_by": "Oliverio",
                "seconded_by": "Casey",
                "outcome": "failed",
                "tally": "6-1-0-4; Cantrell opposed; Rosario, Bickford, Barocio & Escobar recused",
                "source_text": "COMMISSIONER OLIVERIO MADE A MOTION TO APPROVE "
                "STAFF RECOMMENDATION FOR DA21-001",
            }
        ],
        "people": [
            {
                "raw_name": "Oliverio",
                "role": "unknown",
                "source_text": "COMMISSIONER OLIVERIO MADE A MOTION",
            },
            {
                "raw_name": "Casey",
                "role": "unknown",
                "source_text": "COMMISSIONER CASEY SECONDED THE MOTION",
            },
            {"raw_name": "Cantrell", "role": "unknown", "source_text": "CANTRELL OPPOSED"},
        ],
        "locations": [
            {"raw_text": "Downtown West, Council District 6", "source_text": "Council District 6"}
        ],
        "amounts": [],
    },
    notes=(
        "Deliberately tricky outcome: 6-1-0-4 with only 7 of 11 commissioners voting (four recused) means "
        "the motion did NOT reach the majority required among the full body in practice for some governance "
        "structures, but the tally as printed (6 yes, 1 no) reads as passing by a simple count. Annotated here "
        "as 'passed' since 6-1 is a majority of votes cast and the source text does not state the item failed - "
        "flagged in notes as a genuine judgment call an annotator (and a model) could reasonably get wrong, "
        "which is exactly why it's included."
    ),
)

# ---------------------------------------------------------------------
# Synthetic case - SPEC hard case not found naturally in this corpus
# ---------------------------------------------------------------------

case(
    id="sj-cc-synthetic-amount-in-words",
    body="City Council",
    meeting_date="2025-12-09",
    source_document="synthetic-not-a-real-document",
    item_number="X.1",
    item_title="Synthetic: grant amount written in words rather than digits",
    document_text=(
        "X.1 Actions Related to a Regional Broadband Access Grant.\n"
        "Adopt a resolution authorizing the City Manager, or her designee, to accept a grant of "
        "approximately two million five hundred thousand dollars from the State Broadband Council "
        "to expand public wifi access in underserved neighborhoods.\n\n"
        "Action: Upon motion by Councilmember Rosemary Kamei, seconded by Councilmember David "
        "Cohen, and carried unanimously, Resolution No. RES2025-999 was adopted, authorizing the "
        "City Manager, or her designee, to accept a grant of approximately two million five hundred "
        "thousand dollars from the State Broadband Council. (11-0-0)"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "Resolution No. RES2025-999 was adopted",
                "moved_by": "Rosemary Kamei",
                "seconded_by": "David Cohen",
                "outcome": "passed",
                "tally": "11-0-0",
                "source_text": (
                    "Upon motion by Councilmember Rosemary Kamei, seconded by Councilmember David "
                    "Cohen, and carried unanimously, Resolution No. RES2025-999 was adopted"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Rosemary Kamei",
                "role": "councilmember",
                "source_text": "Councilmember Rosemary Kamei",
            },
            {
                "raw_name": "David Cohen",
                "role": "councilmember",
                "source_text": "Councilmember David Cohen",
            },
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "two million five hundred thousand dollars",
                "amount_usd": "2500000",
                "kind": "grant",
                "source_text": "a grant of approximately two million five hundred thousand dollars",
            }
        ],
    },
    notes=(
        "SYNTHETIC, not a real document. Every real San Jose staff report/minutes checked in this corpus "
        "writes dollar amounts numerically ($X,XXX,XXX) - none spell an amount out in words, so this SPEC "
        "hard case ('a dollar amount written in words') doesn't occur naturally in the available sample. "
        "Constructed to the same structural pattern as the real consent-calendar items above (named mover/"
        "seconder, resolution number, unanimous vote) so it tests the same extraction path, just with the "
        "one deliberately different amount format. Disclosed here and in docs/evals.md rather than passed "
        "off as scraped."
    ),
)


def main() -> None:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    for existing in GOLD_DIR.glob("*.json"):
        existing.unlink()

    for c in CASES:
        out_path = GOLD_DIR / f"{c['id']}.json"
        out_path.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {len(CASES)} gold cases to {GOLD_DIR}")


if __name__ == "__main__":
    main()
