"""One-time script: extract and route eight real San Jose City Council
agenda items from the June 9, 2026 meeting - a meeting date the eval
gold set has never seen - to populate the review queue for M4's live
acceptance test.

    ANTHROPIC_API_KEY=... uv run python scripts/run_review_demo_batch.py

Every item's document_text below is verbatim real content from that
meeting's minutes (fetched via civic_scraper.document_text.fetch_and_extract
against the real Legistar PDF, then hand-cleaned of PDF layout whitespace
- the same process build_gold_set.py's cases went through), not
fabricated or paraphrased. Each extraction call routes through llm.py's
cache exactly like every other extraction call in this codebase, so
re-running this script after the first time costs nothing.

This script's job stops at populating data/review_queue/ - the actual
review decisions are made by a human (or, for this milestone's
acceptance test, by a scripted session - see docs/review.md) running
`python -m civic_scraper.review` afterward.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers"))

from civic_scraper.extraction.agenda_item import extract_agenda_item  # noqa: E402
from civic_scraper.review import queue  # noqa: E402
from civic_scraper.review.routing import ItemContext, route_agenda_item  # noqa: E402

JURISDICTION = "San Jose"
BODY = "City Council"
MEETING_DATE = "2026-06-09"
SOURCE_DOCUMENT = "san-jose-city-council-2026-06-09-minutes"

# Shared consent-calendar motion sentence prepended to every 2.x item below,
# exactly as build_gold_set.py does for the Dec 2025 consent items - the
# minutes record one motion covering the whole consent calendar, not one
# per item.
_CONSENT_MOTION = (
    "Action: Upon motion by Councilmember Bien Doan, seconded by Rosemary Kamei, "
    "and carried unanimously, the Consent Calendar was approved as a whole. "
    "The actions below were taken as indicated. (11-0-0)"
)

ITEMS = [
    {
        "item_number": "1.1",
        "item_title": "250th anniversary of the Declaration of Independence proclamation",
        "document_text": (
            "1.1 Councilmember George Casey presented a proclamation recognizing "
            "July 4, 2026, as the 250th anniversary of the Declaration of "
            "Independence of the United States of America, to celebrate the City "
            "of San José's integral role in our nation's history, culture, and "
            "achievements."
        ),
    },
    {
        "item_number": "1.2",
        "item_title": "Philippines Independence Day proclamation",
        "document_text": (
            "1.2 Councilmember Anthony Tordillos presented a proclamation "
            "declaring June 12, 2026 as Philippines Independence Day honoring the "
            "rich cultural heritage, resilience, and contributions of the "
            "Filipino community in San José."
        ),
    },
    {
        "item_number": "1.3",
        "item_title": "Portuguese Heritage Month proclamation",
        "document_text": (
            "1.3 Councilmember Peter Ortiz presented a proclamation declaring "
            "June 2026 as Portuguese Heritage Month honoring the contributions of "
            "the Portuguese Organization for Social Services and Opportunities "
            "(POSSO) to the City of San José."
        ),
    },
    {
        "item_number": "2.2",
        "item_title": "Final adoption of Ordinance No. 31328 (East Village BID)",
        "document_text": (
            f"{_CONSENT_MOTION}\n\n"
            "2.2 Final Adoption of Ordinances. (a) Ordinance No. 31328 - An "
            "Ordinance of the City of San José Establishing the East Village "
            "Business Improvement District Pursuant to the Parking And Business "
            "Improvement Area Law of 1989. [Passed for Publication on 6/2/2026 - "
            "Item 8.1 (26-662)]\n\n"
            "Action: Ordinance No. 31328 was adopted, establishing the East "
            "Village Business Improvement District Pursuant to the Parking And "
            "Business Improvement Area Law of 1989. (11-0-0)"
        ),
    },
    {
        "item_number": "2.8",
        "item_title": "Third Amendment to CSG Advisors consulting agreement",
        "document_text": (
            f"{_CONSENT_MOTION}\n\n"
            "2.8 Third Amendment to the Standard Consultant Agreement with CSG "
            "Advisors Incorporated for Consulting Services. Adopt a resolution "
            "authorizing the Housing Director, or his designee, to negotiate and "
            "execute the Third Amendment to the Standard Consultant Agreement "
            "with CSG Advisors Incorporated, to increase compensation by "
            "$250,000, for a total maximum compensation not to exceed "
            "$1,000,000, for housing finance and development advisory and "
            "housing policy consulting services, for the term ending June 30, "
            "2027.\n\n"
            "Action: Resolution No. RES2026-175 was adopted, authorizing the "
            "Housing Director or his designee to negotiate and execute the Third "
            "Amendment to the Standard Consultant Agreement with CSG Advisors "
            "Incorporated for consulting services. (11-0-0)"
        ),
    },
    {
        "item_number": "2.9",
        "item_title": "Free use of city facilities for the 4th Annual Neighborhoods Conference",
        "document_text": (
            f"{_CONSENT_MOTION}\n\n"
            "2.9 Approval of Free Use of the Rotunda, Wing Meeting Rooms, Council "
            "Chambers, East Plaza, West Plaza, and South Plaza, for the 4th "
            "Annual Neighborhoods Conference. Adopt a resolution authorizing "
            '"Free Use" of the Janet Gray Hayes Rotunda, Wing Meeting Rooms, '
            "Council Chambers, East Plaza, West Plaza, and South Plaza for the "
            "4th Annual Neighborhoods Conference on Saturday, October 3, 2026, "
            "hosted by the Department of Parks, Recreation and Neighborhood "
            "Services.\n\n"
            "Action: Resolution No. RES2026-176 was adopted, authorizing “Free "
            'Use" of the Janet Gray Hayes Rotunda, Wing Meeting Rooms, Council '
            "Chambers, East Plaza, West Plaza, and South Plaza for the 4th Annual "
            "Neighborhoods Conference on Saturday, October 3, 2026, hosted by the "
            "Department of Parks, Recreation and Neighborhood Services. (11-0-0)"
        ),
    },
    {
        "item_number": "2.13",
        "item_title": "Retroactive free use of the Rotunda for the Freedom Ball",
        "document_text": (
            f"{_CONSENT_MOTION}\n\n"
            '2.13 Retroactive Approval of "Free Use" of the Janet Gray Hayes '
            "Rotunda for the African American Community Service Agency's "
            "Juneteenth Power 50 Freedom Ball Sponsored by the Office of Mayor "
            "Matt Mahan as a City Council Sponsored Special Event to Expend City "
            "Funds and Accept Donations of Materials and Services for the Event. "
            "As recommended by the Rules and Open Government Committee on June "
            "3, 2026: (a) Adopt a resolution retroactively authorizing “Free "
            'Use" of the Janet Gray Hayes Rotunda for the private, '
            "invitation-only Power 50: Juneteenth Mayors Freedom Ball scheduled "
            "on June 7, 2026. (b) Retroactively approve the Power 50: Juneteenth "
            "Mayors Freedom Ball scheduled on June 7, 2026 as a City Council "
            "sponsored Special Event and approve the expenditure of funds. (c) "
            "Retroactively approve and accept donations from various "
            "individuals, businesses or community groups to support the "
            "event.\n\n"
            "Action: (a) Resolution No. RES2026-178 was adopted, retroactively "
            "approving the authorization of “Free Use” of the Janet Gray Hayes "
            "Rotunda for the private, invitation-only Power 50: Juneteenth "
            "Mayors Freedom Ball scheduled on June 7, 2026, sponsored by the "
            "Office of Mayor Mahan. (11-0-0)"
        ),
    },
    {
        "item_number": "6.1",
        "item_title": "9885 Wastewater Facility security camera/card reader construction award",
        "document_text": (
            "6.1 Actions Related to the 9885 Regional Wastewater Facility "
            "Security and Access Control Camera and Card Reader Construction "
            "Award. (a) Report on bids and award of a contract for the "
            "construction of the 9885 - Camera and Card Reader Upgrades Project "
            "to the lowest responsive, responsible bidder, Blocka Construction "
            "Inc., in the amount of $11,678,000. (b) Approve a 10% contingency "
            "in the amount of $1,167,800. (c) Adopt the following 2025-2026 "
            "Appropriation Ordinance amendments in the San José-Santa Clara "
            "Treatment Plant Capital Fund: (1) Decrease the Preliminary "
            "Engineering - Water Pollution Control appropriation to the "
            "Environmental Services Department by $1,000,000; (2) Decrease the "
            "Plant Infrastructure Improvements appropriation to the "
            "Environmental Services Department by $1,000,000; and (3) Increase "
            "the Plantwide Security Systems Upgrade to the Environmental "
            "Services Department by $2,000,000.\n\n"
            "Action: Upon motion by Councilmember Domingo Candelas, seconded by "
            "Councilmember Anthony Tordillos, and carried unanimously, (a) the "
            "report on bids and award of a contract for the construction of the "
            "9885 - Camera and Card Reader Upgrades Project to the lowest "
            "responsive, responsible bidder, Blocka Construction Inc., in the "
            "amount of $11,678,000 was accepted; (b) the 10% contingency in the "
            "amount of $1,167,800 was approved; and (c) 2025-2026 Appropriation "
            "Ordinance No. 31331 was adopted, regarding the amendments in the "
            "San José-Santa Clara Treatment Plant Capital Fund. (11-0-0)"
        ),
    },
]


def main() -> None:
    total_published = 0
    total_queued = 0

    for spec in ITEMS:
        item = extract_agenda_item(
            item_title=spec["item_title"],
            item_number=spec["item_number"],
            source_document=SOURCE_DOCUMENT,
            document_text=spec["document_text"],
        )

        context = ItemContext(
            case_id=f"sj-cc-2026-06-09-{spec['item_number']}",
            jurisdiction=JURISDICTION,
            body=BODY,
            meeting_date=MEETING_DATE,
            source_document=SOURCE_DOCUMENT,
            document_text=spec["document_text"],
        )
        result = route_agenda_item(item, context=context)
        queue.save_items(result.queued)

        published_count = (
            len(result.published.motions)
            + len(result.published.people)
            + len(result.published.locations)
            + len(result.published.amounts)
        )
        total_published += published_count
        total_queued += len(result.queued)
        print(
            f"  {spec['item_number']:<6} published={published_count:<3} queued={len(result.queued)}"
        )

    print(f"\nTotal: {total_published} published, {total_queued} sent to review queue.")
    print("Queue status:", queue.summarize())


if __name__ == "__main__":
    main()
