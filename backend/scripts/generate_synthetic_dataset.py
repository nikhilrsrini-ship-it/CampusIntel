"""Create a clearly labeled synthetic request dataset for local demonstrations."""
import argparse
import csv
from pathlib import Path

EXAMPLES = {
    "Examination": ["exam timetable has a conflicting date", "hall ticket is not available for my examination", "result shows an incorrect grade", "revaluation application status is missing", "exam registration payment is not reflected"],
    "Internal Assessment": ["internal assessment marks are incorrect", "assignment score is not visible in the portal", "continuous assessment marks were not entered", "internal marks differ from my evaluated paper", "assessment grade is missing for a course"],
    "Attendance": ["attendance was marked absent by mistake", "class attendance percentage is incorrect", "medical leave attendance record needs correction", "lecture attendance is missing from the portal", "my attendance entry did not sync"],
    "Scholarship": ["scholarship application needs an income certificate", "financial aid payment has not arrived", "scholarship document upload was rejected", "renewal status is pending for my scholarship", "scholarship bank details need correction"],
    "Library": ["library book return is not recorded", "I cannot renew a borrowed book", "library account has a misplaced fine", "catalog search is unavailable", "my library access card is not working"],
    "Hostel": ["hostel room maintenance request", "mess bill amount appears incorrect", "hostel allotment status is pending", "water leak in the residence needs repair", "hostel entry card is not working"],
    "Fee Payment": ["tuition payment is missing from my account", "fee receipt is not available", "online payment failed but money was charged", "installment amount on the portal is incorrect", "payment reference needs verification"],
    "Certificates": ["request for an enrollment certificate", "transcript application is delayed", "I need a bonafide certificate", "degree certificate dispatch status is missing", "official course completion letter request"],
    "Academic Administration": ["course registration needs approval", "department transfer request status", "my program record has the wrong specialization", "academic calendar information is missing", "advisor assignment needs correction"],
    "Technical Support": ["student portal displays a server error", "password reset page is not sending a link", "learning platform cannot open course files", "college app crashes during login", "wifi access credentials are not working"],
    "Other": ["I need help with a general campus service question", "please direct my administrative query", "request for information about campus services", "I am unsure which office handles this issue", "general student service assistance"],
}
PREFIXES = ["Please help: ", "I need assistance because ", "My request is that ", "Could someone review this? ", "I am reporting that "]
SUFFIXES = [".", " and I need an update.", " before the next semester.", "; please advise.", " on my student account."]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/synthetic_requests.csv")
    args = parser.parse_args()
    rows = []
    for category, examples in EXAMPLES.items():
        for index, example in enumerate(examples):
            rows.append({"text": PREFIXES[index] + example + SUFFIXES[index], "category": category, "dataset_type": "SYNTHETIC", "scenario_id": f"{category}-{index}"})
            rows.append({"text": example.capitalize() + SUFFIXES[(index + 2) % len(SUFFIXES)], "category": category, "dataset_type": "SYNTHETIC", "scenario_id": f"{category}-{index}"})
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["text", "category", "dataset_type", "scenario_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} SYNTHETIC rows to {path}; this is demonstration data, not institutional evidence.")


if __name__ == "__main__":
    main()
