"""Hand-written reference data: the "ingredients" the generators draw from.

Everything here is fabricated. Change a number here and the generated data
changes accordingly (and tests that encode the rules will tell you).
"""
from __future__ import annotations

from datetime import date

# code, name, level, tuition per term (INR), has lab fee, popularity weight.
# The order defines program IDs: PRG-001 is the first row.
PROGRAMS = (
    ("BTECH-CS", "B.Tech Computer Science", "UG", 90000, True, 14),
    ("BTECH-ME", "B.Tech Mechanical Engineering", "UG", 80000, True, 6),
    ("BTECH-EE", "B.Tech Electrical Engineering", "UG", 80000, True, 6),
    ("BTECH-CE", "B.Tech Civil Engineering", "UG", 75000, True, 4),
    ("BSC-PHY", "B.Sc Physics", "UG", 35000, True, 4),
    ("BSC-CHEM", "B.Sc Chemistry", "UG", 35000, True, 4),
    ("BSC-MATH", "B.Sc Mathematics", "UG", 30000, False, 4),
    ("BCA", "Bachelor of Computer Applications", "UG", 45000, True, 9),
    ("BBA", "Bachelor of Business Administration", "UG", 50000, False, 9),
    ("BCOM", "B.Com", "UG", 28000, False, 10),
    ("BA-ENG", "B.A. English", "UG", 25000, False, 4),
    ("BA-ECO", "B.A. Economics", "UG", 30000, False, 5),
    ("MTECH-CS", "M.Tech Computer Science", "PG", 95000, True, 3),
    ("MTECH-VLSI", "M.Tech VLSI Design", "PG", 95000, True, 2),
    ("MBA", "Master of Business Administration", "PG", 120000, False, 6),
    ("MCA", "Master of Computer Applications", "PG", 65000, True, 5),
    ("MSC-PHY", "M.Sc Physics", "PG", 40000, True, 2),
    ("MSC-DS", "M.Sc Data Science", "PG", 70000, True, 3),
    ("MA-ENG", "M.A. English", "PG", 30000, False, 1),
    ("MCOM", "M.Com", "PG", 32000, False, 2),
)

# Non-tuition fees per term (INR). LAB applies only to programs with has_lab.
OTHER_FEES = {"LAB": 8000, "LIBRARY": 1500, "TECHNOLOGY": 3000, "ACTIVITY": 2000}

# Term-specific price factor applied to every fee. Summer is a short term;
# Fall carries the yearly fee revision.
TERM_FEE_FACTOR = {
    "TERM-2026-SPRING": "1.00",
    "TERM-2026-SUMMER": "0.60",
    "TERM-2026-FALL": "1.05",
}

# A fee schedule becomes effective this many days before its term starts.
SCHEDULE_LEAD_DAYS = 30

# Scholarship schemes. program_code None = open to all programs;
# max_income_band None = merit-only.
# (name, min_cgpa, max_income_band, program_code, award_type, award_value,
#  max_award_amount, effective_from, effective_to)
SCHEMES = (
    ("Merit Gold", "9.00", None, None, "PERCENT_OF_TUITION", "50", "60000",
     date(2025, 12, 1), None),
    ("Merit Silver", "8.00", None, None, "PERCENT_OF_TUITION", "25", "30000",
     date(2025, 12, 1), None),
    ("Merit Bronze", "7.00", None, None, "PERCENT_OF_TUITION", "10", "12000",
     date(2025, 12, 1), None),
    ("Need Support", "6.00", "LOW", None, "FIXED_AMOUNT", "15000", "15000",
     date(2025, 12, 1), None),
    ("Middle Income Merit", "7.50", "MIDDLE", None, "PERCENT_OF_TUITION", "15", "20000",
     date(2025, 12, 1), None),
    ("CS Excellence", "8.50", None, "BTECH-CS", "PERCENT_OF_TUITION", "20", "25000",
     date(2025, 12, 1), None),
    ("Data Science Fellowship", "8.00", None, "MSC-DS", "FIXED_AMOUNT", "20000", "20000",
     date(2025, 12, 1), None),
    # Expires mid-year, so it can apply to Spring/Summer but not Fall.
    ("First-Half Merit Boost", "7.50", None, None, "PERCENT_OF_TUITION", "10", "10000",
     date(2026, 1, 1), date(2026, 7, 31)),
)

# Fabricated name parts. Combinations are random and any match with a real
# person is coincidental.
FIRST_NAMES = (
    "Aarav", "Aditi", "Aisha", "Ananya", "Arjun", "Ashok", "Biswajit", "Chandan",
    "Debasis", "Deepa", "Divya", "Gaurav", "Harish", "Ishaan", "Jyoti", "Kavya",
    "Kiran", "Lakshmi", "Manas", "Meera", "Mohan", "Nandini", "Neha", "Nikhil",
    "Omkar", "Pooja", "Pradeep", "Priya", "Rahul", "Rakesh", "Rashmi", "Rohan",
    "Sagar", "Sanjay", "Sarita", "Smruti", "Soumya", "Subhashree", "Sunita", "Suresh",
    "Tanvi", "Tapan", "Uday", "Usha", "Varun", "Vikram", "Vimal", "Yash", "Zoya", "Priyanka",
)
LAST_NAMES = (
    "Acharya", "Agarwal", "Bhatt", "Biswal", "Chauhan", "Das", "Dash", "Garg",
    "Gupta", "Iyer", "Jena", "Joshi", "Kapoor", "Khan", "Kumar", "Mahapatra",
    "Mehta", "Mishra", "Mohanty", "Nair", "Naik", "Panda", "Panigrahi", "Patel",
    "Patnaik", "Rao", "Reddy", "Roy", "Sahoo", "Samal", "Sharma", "Singh",
    "Swain", "Tripathy", "Verma",
)
