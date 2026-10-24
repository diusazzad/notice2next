"""
Notice2Next - Synthetic Test Cases & Sample Circulars
Covers 6 distinct evaluation scenarios:
1. Complete notice with explicit actions, dates, and fees.
2. Notice with actionable instruction but omitted deadline (must yield 'NOT STATED').
3. Purely informational notice (advisory / congratulations, 0 actionable teacher tasks).
4. Unrelated historical/reference date (must not be confused with action deadline).
5. Multi-role Bangla notice (distinct duties for homeroom vs lab teachers).
6. Contradictory / ambiguous notice requiring explicit teacher review.
"""

from typing import List, Dict, Any

SAMPLE_NOTICES: List[Dict[str, Any]] = [
    {
        "id": "case_1_complete",
        "title": "Case 1: Complete Circular (Science Exhibition & Field Trip)",
        "language": "en",
        "description": "Standard circular with clear duties, explicit deadlines, responsible groups, and student fee requirements.",
        "expected_items_count": 2,
        "text": (
            "CIRCULAR NO: OHS/2026/OCT-14\n"
            "OAKRIDGE HIGH SCHOOL - ACADEMIC ADMINISTRATION\n"
            "Date: October 24, 2026\n\n"
            "SUBJECT: ANNUAL SCIENCE EXHIBITION REGISTRATION & BOTANICAL FIELD TRIP\n\n"
            "1. All Grade 9 and Grade 10 Science Teachers are hereby instructed to submit the final "
            "roster of student project proposals to the Vice Principal's office by Thursday, October 29, 2026 at 4:00 PM. "
            "Each team must submit a 2-page project synopsis and safety declaration form.\n\n"
            "2. Homeroom Teachers of Grade 8 are requested to collect the botanical garden excursion permission slips "
            "and transport fee of $15 per student. All signed slips and collected fees must be deposited with the accounts counter "
            "by Monday, November 02, 2026 before 12:00 PM.\n\n"
            "Your cooperation in ensuring strict adherence to the above schedule is highly appreciated.\n\n"
            "Sd/-\n"
            "Academic Coordinator, Oakridge High School"
        ),
        "expected_traits": {
            "has_actions": True,
            "has_deadlines": True,
            "has_not_stated": False,
            "parties": ["Grade 9 and Grade 10 Science Teachers", "Homeroom Teachers of Grade 8"]
        }
    },
    {
        "id": "case_2_omitted_deadline",
        "title": "Case 2: Action Stated but Deadline Omitted",
        "language": "en",
        "description": "Instructs teachers to update student health emergency records, but no specific deadline or time is provided. AI must flag NOT STATED.",
        "expected_items_count": 1,
        "text": (
            "INTERNAL MEMORANDUM\n"
            "ST. JUDE'S GRAMMAR SCHOOL - HEALTH & SAFETY CELL\n"
            "Date: October 20, 2026\n\n"
            "TO: ALL HOMEROOM TEACHERS\n"
            "SUBJECT: UPDATING STUDENT EMERGENCY CONTACT & ALLERGY RECORDS\n\n"
            "In accordance with our updated student welfare protocol, all homeroom teachers are required to review "
            "and update the physical allergy cards and emergency guardian phone numbers in the school clinic ledger. "
            "Physical forms may be collected from Nurse Ratched during the morning recess.\n\n"
            "Please ensure that parents sign the updated allergy consent form.\n\n"
            "Regards,\n"
            "School Health Officer"
        ),
        "expected_traits": {
            "has_actions": True,
            "has_deadlines": False,
            "has_not_stated": True,
            "parties": ["All Homeroom Teachers"]
        }
    },
    {
        "id": "case_3_informational",
        "title": "Case 3: Purely Informational Advisory (Zero Tasks)",
        "language": "en",
        "description": "Congratulatory announcement and school library reopening hours. Contains 0 actionable instructions for teachers.",
        "expected_items_count": 0,
        "text": (
            "GENERAL ADVISORY\n"
            "GREEN VALLEY ACADEMY\n"
            "Date: October 22, 2026\n\n"
            "SUBJECT: COMPLETION OF CENTRAL LIBRARY MODERNIZATION & DEBATE TEAM VICTORY\n\n"
            "The School Management is delighted to announce that the Central Library renovation is now complete. "
            "The library now houses over 12,000 reference volumes and an expanded digital research archive. "
            "Regular reading hours for staff and students will be 8:30 AM to 5:00 PM on all instructional days.\n\n"
            "We also extend our heartfelt congratulations to the Senior Debate Team for winning the National Inter-School Championship in Dhaka last weekend.\n\n"
            "We wish everyone a productive academic term.\n\n"
            "Principal, Green Valley Academy"
        ),
        "expected_traits": {
            "has_actions": False,
            "has_deadlines": False,
            "has_not_stated": False,
            "parties": []
        }
    },
    {
        "id": "case_4_unrelated_date",
        "title": "Case 4: Unrelated Historical Date Trap",
        "language": "en",
        "description": "Mentions school founding year (1974) and National Independence Day (March 26) as context, but the only actual task deadline is November 10.",
        "expected_items_count": 1,
        "text": (
            "CIRCULAR REF: DPS/FOUND/2026-88\n"
            "DELHI PUBLIC SCHOOL ARCHIVE COMMITTEE\n"
            "Date: October 18, 2026\n\n"
            "SUBJECT: SUBMISSION OF GOLDEN JUBILEE SOUVENIR ARTICLES\n\n"
            "Since our school's historic founding on September 15, 1974, we have nurtured thousands of exceptional scholars. "
            "In preparation for our 50th Golden Jubilee commemoration and the forthcoming National Day celebration on March 26, "
            "the Archive Committee is curating a memorial commemorative volume.\n\n"
            "Senior Department Subject Heads are required to submit their departmental summary articles (maximum 1,500 words) "
            "and department group photographs to the Editor by Tuesday, November 10, 2026 at 3:00 PM sharp.\n\n"
            "Sd/-\n"
            "Chief Editor & Archive Coordinator"
        ),
        "expected_traits": {
            "has_actions": True,
            "has_deadlines": True,
            "unrelated_dates": ["September 15, 1974", "March 26"],
            "target_deadline": "November 10, 2026 at 3:00 PM sharp",
            "parties": ["Senior Department Subject Heads"]
        }
    },
    {
        "id": "case_5_multi_role_bangla",
        "title": "Case 5: Multi-Role Bangla Notice (শ্রেণি শিক্ষক ও ল্যাব সহকারী)",
        "language": "bn",
        "description": "বাস্তবসম্মত বাংলা স্কুল সার্কুলার। ৯ম ও ১০ম শ্রেণির শ্রেণি শিক্ষক এবং কম্পিউটার ল্যাব সহকারীদের আলাদা দায়িত্ব ও ডেডলাইন।",
        "expected_items_count": 2,
        "text": (
            "স্মারক নং: আইসিএম/২০২৬/বিজ্ঞপ্তি-৮\n"
            "আইডিয়াল মডেল হাই স্কুল ও কলেজ, ঢাকা\n"
            "তারিখ: ২৪ অক্টোবর, ২০২৬\n\n"
            "বিষয়: অর্ধবার্ষিক পরীক্ষার উত্তরপত্র ও ডিজিটাল ক্লাসরুম রিপোর্ট জমা প্রসঙ্গে\n\n"
            "১. ৯ম ও ১০ম শ্রেণির সকল শ্রেণি শিক্ষককে জানানো যাচ্ছে যে, আগামী ২৮ অক্টোবর ২০২৬, বুধবার দুপুর ২:০০ ঘটিকার মধ্যে "
            "শিক্ষার্থীদের মূল্যায়ন নম্বরপত্র ও অনুপস্থিতির চূড়ান্ত তালিকা প্রধান শিক্ষকের কার্যালয়ে জমা দিতে হবে।\n\n"
            "২. কম্পিউটার ল্যাব সহকারী ও আইসিটি শিক্ষকদের আগামী ৩০ অক্টোবর ২০২৬ তারিখের মধ্যে ল্যাবের সকল প্রজেক্টর ও "
            "ইন্টারনেট রাউটারের ত্রৈমাসিক সার্ভিসিং রিপোর্ট আইসিটি ইন-চার্জ বরাবর দাখিল করার নির্দেশ দেওয়া হলো।\n\n"
            "বিষয়টি অতীব জরুরি।\n\n"
            "স্বাক্ষরিত,\n"
            "প্রধান শিক্ষক\n"
            "আইডিয়াল মডেল হাই স্কুল ও কলেজ"
        ),
        "expected_traits": {
            "has_actions": True,
            "has_deadlines": True,
            "parties": ["৯ম ও ১০ম শ্রেণির সকল শ্রেণি শিক্ষক", "কম্পিউটার ল্যাব সহকারী ও আইসিটি শিক্ষক"],
            "deadlines": ["২৮ অক্টোবর ২০২৬, বুধবার দুপুর ২:০০ ঘটিকা", "৩০ অক্টোবর ২০২৬"]
        }
    },
    {
        "id": "case_6_contradictory_malformed",
        "title": "Case 6: Contradictory & Malformed Notice (Human Review Flag)",
        "language": "en",
        "description": "Contains contradictory instructions (submit by 10 AM in body, but 5 PM in footer) and vague responsibilities, triggering validation warning.",
        "expected_items_count": 1,
        "text": (
            "URGENT STAFF NOTE - DRAFT COPY\n"
            "Date: 23/10/2026\n\n"
            "All concerned members may please note that uniform inspection slips should be turned in by 10:00 AM tomorrow morning.\n"
            "However, please note that no slips will be accepted before 5:00 PM due to system maintenance.\n"
            "Teachers or prefects should ensure that the students comply or face administrative actions.\n\n"
            "Note: Details subject to unannounced revision without notice."
        ),
        "expected_traits": {
            "has_actions": True,
            "has_deadlines": True,
            "contradiction": True,
            "requires_human_review": True
        }
    }
]


def get_sample_by_id(sample_id: str) -> Dict[str, Any]:
    """Retrieve a sample notice by ID."""
    for s in SAMPLE_NOTICES:
        if s["id"] == sample_id:
            return s
    return SAMPLE_NOTICES[0]


def get_all_samples_metadata() -> List[Dict[str, Any]]:
    """Return lightweight metadata for UI selector."""
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "language": s["language"],
            "description": s["description"]
        }
        for s in SAMPLE_NOTICES
    ]
