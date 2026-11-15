"""Seed the default request taxonomy and department directory."""
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import Department, RequestCategory

DEPARTMENTS = {
    "EXAM": "Examination Department",
    "REG": "Academic Administration",
    "FIN": "Finance Department",
    "LIB": "Library Services",
    "HOSTEL": "Hostel Administration",
    "IT": "Information Technology",
    "SCH": "Scholarship Office",
}
CATEGORIES = {
    "Examination": ("EXAM", 4),
    "Internal Assessment": ("EXAM", 4),
    "Attendance": ("REG", 3),
    "Scholarship": ("SCH", 4),
    "Library": ("LIB", 2),
    "Hostel": ("HOSTEL", 3),
    "Fee Payment": ("FIN", 4),
    "Certificates": ("REG", 3),
    "Academic Administration": ("REG", 3),
    "Technical Support": ("IT", 3),
    "Other": ("REG", 2),
}


def main() -> None:
    with SessionLocal() as db:
        departments = {}
        for code, name in DEPARTMENTS.items():
            row = db.scalar(select(Department).where(Department.department_code == code))
            if row is None:
                row = Department(department_code=code, department_name=name)
                db.add(row)
                db.flush()
            departments[code] = row
        for name, (code, priority) in CATEGORIES.items():
            if db.scalar(select(RequestCategory.id).where(RequestCategory.category_name == name)) is None:
                db.add(RequestCategory(category_name=name, default_department_id=departments[code].id, priority_weight=priority))
        db.commit()
    print("Default departments and categories are ready.")


if __name__ == "__main__":
    main()
