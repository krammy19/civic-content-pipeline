"""
One-time generator for evals/gold_civicplus/*.json - the second-platform
gold set SPEC's M7 and POLISH's T2.2 ask for.

Every case here is hand-annotated from real Alhambra, CA City Council
minutes (cities.yaml's first `connector: civicplus` entry), fetched live
via CivicPlusConnector + document_text.fetch_and_extract() from
cityofalhambra.org's real AgendaCenter during this session.
document_text is a verbatim excerpt of the real extracted PDF text
(only page-number/date footer furniture removed) - not cleaned up,
not re-typed. That matters here specifically: Alhambra's PDFs extract
with real, pervasive missing-whitespace runs ("AllitemslistedundertheConsent
Agenda...") that San Jose's Legistar-sourced minutes never exhibited.
That is itself a real, reportable difference between the two platforms'
source documents - see docs/evals.md's CivicPlus section - so it is
preserved here rather than normalized away.

These are scored SEPARATELY from evals/gold/ (San Jose), never pooled -
run `uv run python evals/run_eval.py --gold-dir evals/gold_civicplus`
to score this set on its own. Per POLISH's explicit instruction, a
worse score on this set is an expected, honest result, not a bug to
chase: the prompt is not to be tuned against this gold set.

Run once: `uv run python scripts/build_gold_set_civicplus.py`.
Re-running overwrites evals/gold_civicplus/ with the same content.
"""

import json
from pathlib import Path

GOLD_DIR = Path(__file__).resolve().parent.parent / "evals" / "gold_civicplus"

CASES = []


def case(
    id, body, meeting_date, source_document, item_number, item_title, document_text, expected, notes
):
    CASES.append(
        {
            "id": id,
            "jurisdiction": "Alhambra",
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


CC_0209 = "alhambra-city-council-2026-02-09-minutes"
CC_0223 = "alhambra-city-council-2026-02-23-minutes"

# ---------------------------------------------------------------------
# February 9, 2026 - City Council (Consent Agenda, Items 2-11)
# ---------------------------------------------------------------------

case(
    id="alhambra-cc-2026-02-09-2",
    body="City Council",
    meeting_date="2026-02-09",
    source_document=CC_0209,
    item_number="2",
    item_title="Acceptance of grant funds from LACMTA for the 710 Stub arterial conversion",
    document_text=(
        "2. ACCEPTANCE OF GRANT FUNDS FROM THE LOS ANGELES METROPOLITAN "
        "TRANSPORTATION AUTHORITY UNDER MEASURE R FOR THE 710 STUB IMPROVEMENTS "
        "INTO A FOUR-LANE ARTERIAL – F2M19-32, M2M26-28\n\n"
        "On April 24, 2023, the City entered into a Cooperative Agreement with the "
        "California Department of Transportation (Caltrans) for the Project Initiation "
        "Document (PID) for the 710 Stub Improvements at Valley from a six-lane freeway "
        "corridor to a four-lane local arterial. On October 10, 2025, the City received "
        "the Funding Agreement in the amount of $62,400,000 for the City's Arterial "
        "Conversion Project.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council accepted grant funds in the amount of $62,400,000 "
        "from the Los Angeles Metropolitan Transportation Authority under the I-10/SR-710 "
        "Interchange Reconfiguration (Arterial Conversion), LACMTA Project ID #MR1.1.1.01 "
        "and FTIP #LAMIPMR123; appropriated $9,000,000 in revenues and expenditures under "
        "Measure R for the 2024-25, 2025-26 and 2026-27 Fiscal Years, as allocated under "
        "the grant; authorized the City Manager or designee to execute all documents "
        "related to grant implementation; and, directed staff to undertake the steps "
        "necessary to finalize Council's action. (M2M26-28)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council accepted grant funds in the amount of $62,400,000 from "
                    "the Los Angeles Metropolitan Transportation Authority"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$62,400,000",
                "amount_usd": "62400000",
                "kind": "grant",
                "source_text": "the Funding Agreement in the amount of $62,400,000",
            },
            {
                "raw_text": "$9,000,000",
                "amount_usd": "9000000",
                "kind": "grant",
                "source_text": "appropriated $9,000,000 in revenues and expenditures under Measure R",
            },
        ],
    },
    notes="Two distinct dollar figures in one item (the grant total and the appropriated portion) - checks the model doesn't collapse them into one.",
)

case(
    id="alhambra-cc-2026-02-09-3",
    body="City Council",
    meeting_date="2026-02-09",
    source_document=CC_0209,
    item_number="3",
    item_title="Accept Summer Lunch Program grant from the California State Library",
    document_text=(
        "3. ACCEPT SUMMER LUNCH PROGRAM GRANT FROM THE CALIFORNIA STATE LIBRARY "
        "AND APPROPRIATE FUNDS – F2M26-18, M2M26-24\n\n"
        "The California State Library offers grants in support of library programs and "
        "pop-up visits at summer lunch sites to enhance access to books and library "
        "services by the community. In November, 2025, staff applied for this funding "
        "opportunity and was awarded $5,104 to support library programming at the City's "
        "park sites participating under the free Summer Lunch Program.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council accepted $5,104 in grant funds from the California "
        "State Library to support the Library's mobile summer programs and services; "
        "appropriated revenue and expenditure funds in the amount of $5,104; authorized "
        "the City Manager or designee to sign the grant agreement with the California "
        "State Library, subject to final language approval by the City Manager and City "
        "Attorney; and, directed staff to undertake the steps necessary to finalize "
        "Council's action. (M2M26-24)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
        "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": "City Council accepted $5,104 in grant funds from the California State Library",
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maloney",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
                    "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maloney", "role": "mayor", "source_text": "Seconded: MALONEY"},
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$5,104",
                "amount_usd": "5104",
                "kind": "grant",
                "source_text": "was awarded $5,104 to support library programming",
            }
        ],
    },
    notes="Small dollar amount ($5,104) - checks the model doesn't only pick up large, round figures. Maloney is the Mayor, not a bare councilmember.",
)

case(
    id="alhambra-cc-2026-02-09-4",
    body="City Council",
    meeting_date="2026-02-09",
    source_document=CC_0209,
    item_number="4",
    item_title="Award contract for the Solid Waste Management Services Agreement audit",
    document_text=(
        "4. AWARD CONTRACT: ALHAMBRA SOLID WASTE MANAGEMENT SERVICES AGREEMENT "
        "AUDIT – F2M25-66, RFP2M25-28, C2M26-10, M2M26-25\n\n"
        "On December 8, 2025, the City Council approved staff's recommendation to solicit "
        "proposals for professional services to audit the Solid Waste Management Services "
        "Agreement with Republic Services. Five proposals were received. HF&H Consultants "
        "ranked highest.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council approved a contract, subject to final approval by the "
        "City Manager and the City Attorney, by and between the City of Alhambra and "
        "HF&H Consultants, LLC, for professional services in the amount of $70,000 for a "
        "Waste Audit for Rate Year 2023-24 under the Solid Waste Management Services "
        "Agreement with Republic Services; and, directed staff to undertake the steps "
        "necessary to finalize Council's action. (M2M26-25)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
        "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council approved a contract ... with HF&H Consultants, LLC, for "
                    "professional services in the amount of $70,000"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maloney",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
                    "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maloney", "role": "mayor", "source_text": "Seconded: MALONEY"},
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$70,000",
                "amount_usd": "70000",
                "kind": "contract",
                "source_text": "for professional services in the amount of $70,000",
            }
        ],
    },
    notes="Contractor name (HF&H Consultants, LLC) is a business, not a person - checks the model doesn't extract it as a person.",
)

case(
    id="alhambra-cc-2026-02-09-5",
    body="City Council",
    meeting_date="2026-02-09",
    source_document=CC_0209,
    item_number="5",
    item_title="Renewal of Edison easement license agreement on Raymond Avenue",
    document_text=(
        "5. RENEWAL OF EDISON EASEMENT LICENSE AGREEMENT – F2M21-30, F2M1-44, "
        "C2M26-11, M2M26-26\n\n"
        "In 1986, the City of Alhambra entered into a license agreement with SCE to lease "
        "the easement on Raymond Avenue between Alhambra Road and Cedar Avenue. In March "
        "2021, the license agreement was renewed for a five-year period, and would expire "
        "on March 31, 2026. SCE has offered a five-year renewal of the license agreement "
        "from April 1, 2026, through March 31, 2031. The license agreement would include "
        "an annual fee of $581.37 that would increase annually by no more than 5%.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council approved the renewal of the license agreement with "
        "Southern California Edison Company, subject to final language approval by the "
        "City Manager and City Attorney, for the use of the easement on Raymond Avenue "
        "adjacent to Alhambra Park for the purpose of park use, for a period of five (5) "
        "years, commencing on April 1, 2026 through March 31, 2031, with an annual fee of "
        "$581.37 plus annual increases not to exceed 5% payable to Southern California "
        "Edison; and, directed staff to undertake the steps necessary to finalize "
        "Council's action. (M2M26-26)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
        "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council approved the renewal of the license agreement with "
                    "Southern California Edison Company"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maloney",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
                    "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maloney", "role": "mayor", "source_text": "Seconded: MALONEY"},
        ],
        "locations": [
            {
                "raw_text": "Raymond Avenue easement adjacent to Alhambra Park",
                "source_text": "the easement on Raymond Avenue adjacent to Alhambra Park",
            }
        ],
        "amounts": [
            {
                "raw_text": "$581.37",
                "amount_usd": "581.37",
                "kind": "fee",
                "source_text": "with an annual fee of $581.37 plus annual increases",
            }
        ],
    },
    notes="A sub-$1,000 recurring fee (not a one-time contract) - checks the model picks 'fee' as the kind, and extracts a real street-level location.",
)

case(
    id="alhambra-cc-2026-02-09-7",
    body="City Council",
    meeting_date="2026-02-09",
    source_document=CC_0209,
    item_number="7",
    item_title="Street easement acceptance at 1000-1008 South Garfield Avenue",
    document_text=(
        "7. STREET EASEMENT: 1000-1008 SOUTH GARFIELD AVENUE – F2M26-8, M2M26-27, "
        "D2M26-2038\n\n"
        "Staff requested that the City Council accept a street easement for the property "
        "located at 1000-1008 S. Garfield Avenue. Per the City of Alhambra Right-Of-Way "
        "and Lane Configuration Study of 1985, a dedication of the north west corner of "
        "the lot (Garfield Ave. and Linda Vista Ave.) was required.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council adopted Minute Order No. M2M26-27 accepting that "
        "certain Easement (Deed No. D2M26-2038) from Buddhist Tzu Chi Foundation granting "
        "to the City of Alhambra an easement for public streets and highways and public "
        "utility purposes; and, directed staff to undertake the steps necessary to "
        "finalize Council's action.\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
        "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council adopted Minute Order No. M2M26-27 accepting that certain "
                    "Easement (Deed No. D2M26-2038) from Buddhist Tzu Chi Foundation"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maloney",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
                    "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maloney", "role": "mayor", "source_text": "Seconded: MALONEY"},
        ],
        "locations": [
            {
                "raw_text": "1000-1008 South Garfield Avenue",
                "source_text": "STREET EASEMENT: 1000-1008 SOUTH GARFIELD AVENUE",
            }
        ],
        "amounts": [],
    },
    notes="A street-address location with no dollar amount at all - checks the model doesn't invent a fee where the source states none. 'Buddhist Tzu Chi Foundation' is the easement grantor, not a person.",
)

case(
    id="alhambra-cc-2026-02-09-8",
    body="City Council",
    meeting_date="2026-02-09",
    source_document=CC_0209,
    item_number="8",
    item_title="Nominate an appointee for the Metro San Gabriel Valley Service Council",
    document_text=(
        "8. NOMINATE AN APPOINTEE FOR METRO SAN GABRIEL VALLEY SERVICE COUNCIL "
        "– F2M26-16, M2M26-29\n\n"
        "San Gabriel City Council Member John Wu currently serves on behalf of the Cities "
        "of Alhambra, San Gabriel, San Marino, and South Pasadena as an appointee on "
        "Metro's San Gabriel Valley (SGV) Service Council. His term will expire on June "
        "30, 2026. Councilmember Wu wishes to continue serving on the SGV Service Council.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council voted to nominate San Gabriel City Council Member "
        "John Wu as an appointee to the Metro San Gabriel Valley Service Council; and, "
        "directed staff to undertake the steps necessary to finalize Council's action. "
        "(M2M26-29)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
        "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council voted to nominate San Gabriel City Council Member John "
                    "Wu as an appointee to the Metro San Gabriel Valley Service Council"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maloney",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
                    "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "John Wu",
                "role": "public",
                "source_text": "San Gabriel City Council Member John Wu",
            },
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maloney", "role": "mayor", "source_text": "Seconded: MALONEY"},
        ],
        "locations": [],
        "amounts": [],
    },
    notes="John Wu is a council member of a DIFFERENT city (San Gabriel), not Alhambra - annotated 'public' rather than 'councilmember' since he holds no office on this body. A real test of role attribution beyond a name-title pattern match.",
)

case(
    id="alhambra-cc-2026-02-09-11",
    body="City Council",
    meeting_date="2026-02-09",
    source_document=CC_0209,
    item_number="11",
    item_title="Introduction of an ordinance setting school-zone speed limits",
    document_text=(
        "11. CONSIDERATION AND INTRODUCTION FOR FIRST READING OF AN ORDINANCE "
        "ADOPTING THE PRIMA FACIE SPEED LIMITS IN SCHOOL ZONES IN THE CITY – "
        "F2M26-7, O2M26-4857\n\n"
        "The recent passage of AB 382 enabled cities to reduce the speed limit in school "
        "zones to 20 miles per hour when children are present. At the January 12, 2026 "
        "City Council meeting, Councilwoman Adele Andrade-Stadler requested that an item "
        "be agendized setting a speed limit of 20 miles per hour for the Council's "
        "consideration.\n\n"
        "Discussion: Vice Mayor ANDRADE-STADLER thanked staff for the changes to speed "
        "limits in school zones.\n\n"
        "Action Taken: City Council declared introduced for its first reading the "
        "following ordinance entitled: Ordinance No. O2M26-4857: An Ordinance of the "
        "Alhambra City Council adding Section 11.08.075 to Chapter 11.08 of the Alhambra "
        "Municipal Code establishing a prima facia speed limit of 20 miles per hour in "
        "school zones, which ordinance would return for a second reading and adoption "
        "the next regular City Council meeting.\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
        "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council declared introduced for its first reading Ordinance No. "
                    "O2M26-4857 establishing a prima facia speed limit of 20 miles per hour "
                    "in school zones"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maloney",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MALONEY\n"
                    "Ayes: MAZA, ANDRADE-STADLER, LEE, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Adele Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Councilwoman Adele Andrade-Stadler requested that an item be agendized",
            },
            {"raw_name": "Maloney", "role": "mayor", "source_text": "Seconded: MALONEY"},
        ],
        "locations": [],
        "amounts": [],
    },
    notes="An ordinance's FIRST reading (introduction), not final adoption - outcome is still 'passed' for the introduction vote itself, not a second-reading adoption. Full first name available for Andrade-Stadler here, unlike other items in this same document.",
)

# ---------------------------------------------------------------------
# February 23, 2026 - City Council (Consent Agenda, Items 6-13)
# ---------------------------------------------------------------------

case(
    id="alhambra-cc-2026-02-23-6",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="6",
    item_title="Award contract for the Seventh Street water main replacement project",
    document_text=(
        "6. AWARD CONTRACT: WATER MAIN REPLACEMENT PROJECT ON SEVENTH STREET "
        "BETWEEN VALLEY BOULEVARD AND SHORB STREET – F2M25-63, N2M25-174, "
        "C2M26-12, M2M26-30\n\n"
        "On December 8, 2025, the City Council approved the distribution of Notice "
        "Inviting Bids for the Water Main Replacement Seventh Street from Valley "
        "Boulevard to Shorb Street. On February 5, 2026, bids were opened by the City "
        "Clerk. Five bids were received, which ranged from amount of $444,760.00 to the "
        "high bid of $726,250. Ramona Inc. submitted the lowest qualified bid at "
        "$444,760.00.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council awarded a contract, subject to final language "
        "approval by the City Manager and City Attorney, by and between the City of "
        "Alhambra and Ramona Inc. for the Water Main Replacement on Seventh Street from "
        "Valley Boulevard to Shorb Street in an amount not to exceed $444,760.00; "
        "determined that the Water Main Replacement Seventh Street from Valley Boulevard "
        "to Shorb Street Project is categorically exempt from the California "
        "Environmental Quality Act (CEQA) pursuant to CEQA Guidelines Section 15301 (b); "
        "and, directed staff to undertake the steps necessary to finalize the Council's "
        "action. (M2M26-30)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council awarded a contract ... to Ramona Inc. for the Water Main "
                    "Replacement on Seventh Street ... in an amount not to exceed $444,760.00"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [
            {
                "raw_text": "Seventh Street between Valley Boulevard and Shorb Street",
                "source_text": "WATER MAIN REPLACEMENT PROJECT ON SEVENTH STREET BETWEEN VALLEY BOULEVARD AND SHORB STREET",
            }
        ],
        "amounts": [
            {
                "raw_text": "$444,760.00",
                "amount_usd": "444760.00",
                "kind": "contract",
                "source_text": "in an amount not to exceed $444,760.00",
            }
        ],
    },
    notes="Two other bid amounts ($726,250 high bid, and the range) appear in the background paragraph but were NOT awarded - only the actual contract amount counts as the item's amount. Tests whether the model over-extracts every dollar figure mentioned versus only the one actually acted on.",
)

case(
    id="alhambra-cc-2026-02-23-7",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="7",
    item_title="Award contract for the Poplar Boulevard rehabilitation project",
    document_text=(
        "7. AWARD CONTRACT: POPLAR BOULEVARD REHABILITATION PROJECT (STPL-5130(024)) "
        "– F2M25-55, N2M25-145, C2M26-13, M2M26-31\n\n"
        "The Notice Inviting Bids for the Poplar Boulevard Rehabilitation Project was "
        "approved for distribution by the City Council on October 13, 2025. On December "
        "4, 2025, the City Clerk received eight bids that ranged from $673,956.00 to "
        "$1,098,496.00. Staff reviewed the bids and found the one received from Gentry "
        "Brothers, Inc. in the amount of $673,956 to be the lowest responsible bid.\n\n"
        "Discussion: None\n\n"
        "Action Taken: City Council awarded a contract, subject to final language "
        "approval by the City Manager and City Attorney, to Gentry Brothers, Inc. in the "
        "amount of $673,956.00 for the Poplar Boulevard Rehabilitation Project "
        "(HSIP-5130(024)); and, directed staff to undertake the steps necessary to "
        "finalize the Council's action. (M2M26-31)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council awarded a contract ... to Gentry Brothers, Inc. in the "
                    "amount of $673,956.00 for the Poplar Boulevard Rehabilitation Project"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [
            {
                "raw_text": "Poplar Boulevard",
                "source_text": "AWARD CONTRACT: POPLAR BOULEVARD REHABILITATION PROJECT",
            }
        ],
        "amounts": [
            {
                "raw_text": "$673,956.00",
                "amount_usd": "673956.00",
                "kind": "contract",
                "source_text": "to Gentry Brothers, Inc. in the amount of $673,956.00",
            }
        ],
    },
    notes="Same shape as item 6 (multiple bid figures, only one awarded) - a second real instance of the same over-extraction risk, from a different vendor and street.",
)

case(
    id="alhambra-cc-2026-02-23-8",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="8",
    item_title="Notice of completion for the golf course parking area landscape project",
    document_text=(
        "8. NOTICE OF COMPLETION: GOLF COURSE PARKING AREA LANDSCAPE ENHANCEMENT "
        "PROJECT – F2M25-46, C2M25-43, M2M26-32\n\n"
        "On October 13, 2025, the City Council awarded a contract to Four Seasons "
        "Landscaping Inc. in the amount of $109,000 for the Golf Course Parking Area "
        "Landscape Enhancement project. The City requested a change order to remove the "
        "old dying trees in the landscaping area which totaled $16,000, which brings the "
        "contract total to $125,000.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council accepted the work of SGD Enterprises DBA Four "
        "Seasons Landscaping, Inc. for the Alhambra Golf Course Parking Area Landscape "
        "Enhancement Project as complete in the amount of $125,000.00; directed the City "
        "Clerk to file a Notice of Completion with the County of Los Angeles for "
        "recordation; instructed the Finance Director to release the 5% retention 35 "
        "days from the date of recordation if no liens and filed; and, directed staff to "
        "undertake the steps necessary to finalize Council's action. (M2M25-32)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council accepted the work of SGD Enterprises DBA Four Seasons "
                    "Landscaping, Inc. ... as complete in the amount of $125,000.00"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [
            {
                "raw_text": "Alhambra Golf Course Parking Area",
                "source_text": "GOLF COURSE PARKING AREA LANDSCAPE ENHANCEMENT PROJECT",
            }
        ],
        "amounts": [
            {
                "raw_text": "$125,000.00",
                "amount_usd": "125000.00",
                "kind": "contract",
                "source_text": "as complete in the amount of $125,000.00",
            }
        ],
    },
    notes="The final accepted amount ($125,000) is the ORIGINAL contract ($109,000) plus a change order ($16,000) - a genuine test of whether the model reports the final total actually acted on versus one of the two contributing figures.",
)

case(
    id="alhambra-cc-2026-02-23-9",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="9",
    item_title="Notice of completion for the 2024 CDBG ADA ramp project",
    document_text=(
        "9. NOTICE OF COMPLETION: 2024 CDBG ADA RAMP PROJECT – F2M25-26, "
        "C2M25-17, M2M26-34\n\n"
        "On April 28, 2025, the City Council awarded a contract to CJ Concrete, Inc. for "
        "the 2024 CDBG ADA Ramp Project in the amount of $638,125.00. One change order "
        "was issued resulting in an increase of $21,193.50 for an additional ramp, "
        "making the final cost $659,318.50.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council accepted the work of CJ Concrete Construction, Inc. "
        "for the 2024 CDBG ADA Ramp Project as complete in the amount of $659,318.50; "
        "directed the City Clerk to file a Notice of Completion with the County of Los "
        "Angeles for recordation; instructed the Finance Director to release the 5% "
        "retention 35 days from the date of recordation if no liens are filed; and, "
        "directed staff to undertake the steps necessary to finalize the Council's "
        "action. (M2M26-34)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council accepted the work of CJ Concrete Construction, Inc. for "
                    "the 2024 CDBG ADA Ramp Project as complete in the amount of $659,318.50"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$659,318.50",
                "amount_usd": "659318.50",
                "kind": "contract",
                "source_text": "as complete in the amount of $659,318.50",
            }
        ],
    },
    notes="Same original-plus-change-order pattern as item 8 ($638,125.00 + $21,193.50 = $659,318.50) - a second real instance to check this isn't a one-off. No specific street address given for this item, unlike most others.",
)

case(
    id="alhambra-cc-2026-02-23-10",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="10",
    item_title="Grant agreement with San Gabriel Valley Municipal Water District",
    document_text=(
        "10. GRANT AGREEMENT WITH SAN GABRIEL VALLEY MUNICIPAL WATER DISTRICT TO "
        "SUPPORT THE CITY'S COMPREHENSIVE WATER MASTER PLAN UPDATE – F2M25-51, "
        "F2M26-18, M2M26-35\n\n"
        "The San Gabriel Valley Municipal Water District (SGVMWD) provides reliable "
        "supplemental water for the communities of Alhambra, Azusa, Monterey Park, and "
        "Sierra Madre. The City applied for financial assistance via the SGVMWD's FY2025 "
        "City Grant Program to update the City's Water Master Plan (WMP).\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council approved a Grant Agreement to receive an amount of "
        "$50,000.00 from the San Gabriel Valley Municipal Water District to provide "
        "support in the development of the City's comprehensive Water Master Plan (WMP); "
        "and, directed staff to undertake the steps necessary to finalize Council's "
        "action. (M2M26-35)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council approved a Grant Agreement to receive an amount of "
                    "$50,000.00 from the San Gabriel Valley Municipal Water District"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$50,000.00",
                "amount_usd": "50000.00",
                "kind": "grant",
                "source_text": "to receive an amount of $50,000.00 from the San Gabriel Valley Municipal Water District",
            }
        ],
    },
    notes="A grant the City receives (income), the mirror image of items 6-9's contract awards (spending) - checks the model doesn't default every dollar figure to 'contract'.",
)

case(
    id="alhambra-cc-2026-02-23-11",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="11",
    item_title="Notice inviting bids for City Hall HVAC controls retrofit",
    document_text=(
        "11. NOTICE INVITING BIDS: CITY HALL ENERGY MANAGEMENT SYSTEM HVAC CONTROLS "
        "RETROFIT AND UPGRADE – F2M26-25, N2M26-20\n\n"
        "The City Hall Energy Management System (EMS) is beyond its useful life, and it "
        "is no longer supported by the manufacturer. This project would remove and "
        "replace the aging system with new hardware and furnish and install new controls "
        "and sensors needed for the new system.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council authorized staff to issue a Notice Inviting Bids to "
        "prospective contractors for the City Hall Energy Management System (EMS) HVAC "
        "Controls retrofit and upgrade, with bids due no later than 10:30 a.m. on April "
        "2, 2026, and opened on 11:00 a.m. that same day; and, directed staff to "
        "undertake the steps necessary to finalize the Council's action.\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council authorized staff to issue a Notice Inviting Bids to "
                    "prospective contractors for the City Hall Energy Management System "
                    "(EMS) HVAC Controls retrofit and upgrade"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [
            {"raw_text": "City Hall", "source_text": "CITY HALL ENERGY MANAGEMENT SYSTEM"}
        ],
        "amounts": [],
    },
    notes="A bid solicitation, not an award - no dollar amount exists yet at this stage, since bids haven't been opened. Checks the model doesn't invent a figure for a not-yet-priced project.",
)

case(
    id="alhambra-cc-2026-02-23-12",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="12",
    item_title="Notice inviting bids for City Hall south structure roof replacement",
    document_text=(
        "12. NOTICE INVITING BIDS: ROOF REPLACEMENT AT CITY HALL (SOUTH STRUCTURE) "
        "– F2M26-26, N2M26-21\n\n"
        "The roof at the south side of City Hall was over 20-plus years old, and it was "
        "in need of replacement. Water damage in the Parks and Recreation Department was "
        "observed. The recommendation was to remove the existing roof and underlayment, "
        "and repair any damaged decking.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council authorized staff to issue a notice inviting bids to "
        "prospective contractors for Roof Replacement at Alhambra City Hall, with bids "
        "due no later than 10:30 a.m. on April 2, 2026 and opened on 11:00 a.m. that same "
        "day; and, directed staff to undertake the steps necessary to finalize the "
        "Council's action.\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council authorized staff to issue a notice inviting bids to "
                    "prospective contractors for Roof Replacement at Alhambra City Hall"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [
            {
                "raw_text": "City Hall (south structure)",
                "source_text": "ROOF REPLACEMENT AT CITY HALL (SOUTH STRUCTURE)",
            }
        ],
        "amounts": [],
    },
    notes="Same bid-solicitation-with-no-amount-yet shape as item 11, and the same 'City Hall' location string as item 11 but a different building side - checks the model treats these as two distinct items rather than merging them.",
)

case(
    id="alhambra-cc-2026-02-23-13",
    body="City Council",
    meeting_date="2026-02-23",
    source_document=CC_0223,
    item_number="13",
    item_title="Contract amendment for City Engineering Services, FY 2025-2026",
    document_text=(
        "13. CONTRACT AMENDMENT: CITY ENGINEERING SERVICES FOR FY 2025-2026 – "
        "F2M2-57, C2M2-46, M2M26-36\n\n"
        "Transtech Engineers has provided City Engineering Services to the Public Works "
        "Department on an as needed basis. Due to the increased amount of Accessory "
        "Dwelling Unit plan checks and Traffic Studies during Fiscal Year 2025-2026, "
        "Transtech was required to do work that exceeded the contract amount by "
        "$200,00.00.\n\n"
        "Discussion: None.\n\n"
        "Action Taken: City Council approved an amendment to the Agreement with "
        "Transtech Engineers for Fiscal Year 2025-2026 for an additional $200,000.00; "
        "authorized the City Manager to sign the Agreement on behalf of the City "
        "Council; and, directed staff to undertake the steps necessary to finalize "
        "Council's action. (M2M26-36)\n"
        "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
        "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
        "Noes: NONE\n"
        "Absent: NONE"
    ),
    expected={
        "item_type": "consent",
        "motions": [
            {
                "text": (
                    "City Council approved an amendment to the Agreement with Transtech "
                    "Engineers for Fiscal Year 2025-2026 for an additional $200,000.00"
                ),
                "moved_by": "Andrade-Stadler",
                "seconded_by": "Maza",
                "outcome": "passed",
                "tally": "5-0-0",
                "source_text": (
                    "Vote: Moved: ANDRADE-STADLER Seconded: MAZA\n"
                    "Ayes: LEE, MAZA, ANDRADE-STADLER, WANG, MALONEY\n"
                    "Noes: NONE\n"
                    "Absent: NONE"
                ),
            }
        ],
        "people": [
            {
                "raw_name": "Andrade-Stadler",
                "role": "councilmember",
                "source_text": "Moved: ANDRADE-STADLER",
            },
            {"raw_name": "Maza", "role": "councilmember", "source_text": "Seconded: MAZA"},
        ],
        "locations": [],
        "amounts": [
            {
                "raw_text": "$200,000.00",
                "amount_usd": "200000.00",
                "kind": "contract",
                "source_text": "for an additional $200,000.00",
            }
        ],
    },
    notes="A real typo in the source PDF ('$200,00.00' in the background paragraph, missing a zero) versus the correct '$200,000.00' in the Action Taken clause used for the actual vote - the gold amount is the one actually acted on, not the typo'd one. A genuine document-quality artifact, not a fabricated hard case.",
)

if __name__ == "__main__":
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    for old in GOLD_DIR.glob("*.json"):
        old.unlink()
    for c in CASES:
        (GOLD_DIR / f"{c['id']}.json").write_text(
            json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(CASES)} cases to {GOLD_DIR}")
