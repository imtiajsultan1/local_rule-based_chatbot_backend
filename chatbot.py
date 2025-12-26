import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


COURSE_CODE_RE = re.compile(r"\b([A-Z]{3})\s?(\d{3})\b")
SEMESTER_RE = re.compile(r"\b(Spring|Summer|Fall|Autumn|Winter)\s+\d{4}\b", re.IGNORECASE)


def load_courses() -> List[Dict]:
    data_path = Path(__file__).resolve().parent / "data" / "courses.json"
    with data_path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


class CourseChatbot:
    def __init__(self, data: List[Dict], kg=None):
        self.data = data
        self.kg = kg
        self.by_code = {c["course"].upper(): c for c in data}
        self.teacher_names = sorted({c["teacher"] for c in data}, key=len, reverse=True)
        self.dept_names = sorted({c["dept"] for c in data}, key=len, reverse=True)
        self.semester_names = sorted({c["semester"] for c in data}, key=len, reverse=True)
        dept_pattern = "|".join(re.escape(name) for name in self.dept_names)
        self.dept_re = re.compile(rf"\b({dept_pattern})\b", re.IGNORECASE) if dept_pattern else None

    def process(self, text: str) -> Tuple[str, str, Dict]:
        entities = self.extract_entities(text)
        intent = self.detect_intent(text, entities)
        reply = self.build_reply(intent, entities)
        return reply, intent, entities

    def extract_entities(self, text: str) -> Dict:
        text_upper = text.upper()
        text_lower = text.lower()
        code_match = COURSE_CODE_RE.search(text_upper)
        course_code = None
        if code_match:
            course_code = f"{code_match.group(1)}{code_match.group(2)}"

        teacher = self._match_from_list(text_lower, self.teacher_names)
        dept = None
        if self.dept_re:
            dept_match = self.dept_re.search(text_upper)
            if dept_match:
                dept = dept_match.group(1).upper()

        semester = None
        semester_match = SEMESTER_RE.search(text)
        if semester_match:
            season = semester_match.group(1).title()
            year = semester_match.group(0).split()[-1]
            semester = f"{season} {year}"

        return {
            "course_code": course_code,
            "teacher": teacher,
            "dept": dept,
            "semester": semester,
        }

    def detect_intent(self, text: str, entities: Dict) -> str:
        text_lower = text.lower()

        if any(k in text_lower for k in ["help", "commands", "what can you do"]):
            return "help"
        if "graph" in text_lower or "kg" in text_lower:
            return "graph_show"

        if entities.get("course_code"):
            if any(k in text_lower for k in ["teacher", "teach", "teaches", "instructor"]):
                return "course_teacher"
            if any(k in text_lower for k in ["title", "name"]):
                return "course_title"
            if any(k in text_lower for k in ["credit", "credits"]):
                return "course_credit"
            if any(k in text_lower for k in ["semester", "term"]):
                return "course_semester"
            return "course_info"

        if entities.get("teacher") and any(k in text_lower for k in ["courses", "teach", "teaches"]):
            return "teacher_courses"
        if entities.get("dept") and any(k in text_lower for k in ["department", "dept", "courses"]):
            return "dept_courses"
        if entities.get("semester") and any(k in text_lower for k in ["courses", "offered"]):
            return "semester_courses"

        return "unknown"

    def build_reply(self, intent: str, entities: Dict) -> str:
        kg_ok, kg_error = self._kg_status()
        warning = ""
        if self.kg is not None and not kg_ok:
            warning = " Neo4j down, dataset result dekhacchi."

        if intent == "help":
            return (
                "Commands: course teacher/title/credit/semester, teacher courses, dept courses, "
                "semester courses, graph status. (Try: 'who teaches CSE411', 'CSE dept courses')"
            )

        if intent == "graph_show":
            if self.kg is None or not kg_ok:
                return "Graph unavailable. Neo4j is not running."
            summary, error = self.kg.summary()
            if error or summary is None:
                return "Graph summary not available right now."
            return (
                f"Graph summary: {summary['nodes']} nodes, {summary['edges']} edges. "
                f"(KG has {summary['nodes']} nodes and {summary['edges']} edges.)"
            )

        if intent == "course_teacher":
            course = self._get_course(entities.get("course_code"))
            if not course:
                return "Course code not found. (No matching course.)"
            self._try_upsert(course, kg_ok)
            code = course["course"]
            teacher = course["teacher"]
            return (
                f"{code} course er teacher: {teacher}. (Teacher of {code} is {teacher}.)" + warning
            )

        if intent == "course_title":
            course = self._get_course(entities.get("course_code"))
            if not course:
                return "Course code not found. (No matching course.)"
            self._try_upsert(course, kg_ok)
            code = course["course"]
            title = course["title"]
            return f"{code} course er title: {title}. (Title of {code} is {title}.)" + warning

        if intent == "course_credit":
            course = self._get_course(entities.get("course_code"))
            if not course:
                return "Course code not found. (No matching course.)"
            self._try_upsert(course, kg_ok)
            code = course["course"]
            credit = course["credit"]
            return f"{code} course er credit: {credit}. (Credits of {code} are {credit}.)" + warning

        if intent == "course_semester":
            course = self._get_course(entities.get("course_code"))
            if not course:
                return "Course code not found. (No matching course.)"
            self._try_upsert(course, kg_ok)
            code = course["course"]
            semester = course["semester"]
            return (
                f"{code} course offered in: {semester}. "
                f"({code} is offered in {semester}.)" + warning
            )

        if intent == "course_info":
            course = self._get_course(entities.get("course_code"))
            if not course:
                return "Course code not found. (No matching course.)"
            self._try_upsert(course, kg_ok)
            code = course["course"]
            title = course["title"]
            teacher = course["teacher"]
            credit = course["credit"]
            semester = course["semester"]
            return (
                f"{code}: {title}, {teacher}, {credit} credit, {semester}. "
                f"({code} course info: {title}, teacher {teacher}, "
                f"{credit} credits, offered in {semester}.)" + warning
            )

        if intent == "teacher_courses":
            teacher = entities.get("teacher")
            if not teacher:
                return "Teacher name not found. (Try a full name.)"
            courses = []
            if self.kg is not None and kg_ok:
                courses, _ = self.kg.get_courses_by_teacher(teacher)
            if not courses:
                courses = [
                    {"code": c["course"], "title": c["title"]}
                    for c in self.data
                    if c["teacher"] == teacher
                ]
            if not courses:
                return "No courses found for that teacher."
            for course in courses:
                record = self.by_code.get(course["code"].upper())
                if record:
                    self._try_upsert(record, kg_ok)
            course_list = ", ".join(c["code"] for c in courses)
            return (
                f"{teacher} er courses: {course_list}. "
                f"(Courses taught by {teacher}: {course_list}.)" + warning
            )

        if intent == "dept_courses":
            dept = entities.get("dept")
            if not dept:
                return "Department not found. (Try: CSE department courses.)"
            courses = []
            if self.kg is not None and kg_ok:
                courses, _ = self.kg.get_courses_by_dept(dept)
            if not courses:
                courses = [
                    {"code": c["course"], "title": c["title"]}
                    for c in self.data
                    if c["dept"].upper() == dept.upper()
                ]
            if not courses:
                return "No courses found for that department."
            for course in courses:
                record = self.by_code.get(course["code"].upper())
                if record:
                    self._try_upsert(record, kg_ok)
            course_list = ", ".join(c["code"] for c in courses)
            return (
                f"{dept} department er courses: {course_list}. "
                f"(Courses in {dept} department: {course_list}.)" + warning
            )

        if intent == "semester_courses":
            semester = entities.get("semester")
            if not semester:
                return "Semester not found. (Try: Spring 2025 courses.)"
            courses = []
            if self.kg is not None and kg_ok:
                courses, _ = self.kg.get_courses_by_semester(semester)
            if not courses:
                courses = [
                    {"code": c["course"], "title": c["title"]}
                    for c in self.data
                    if c["semester"].lower() == semester.lower()
                ]
            if not courses:
                return "No courses found for that semester."
            for course in courses:
                record = self.by_code.get(course["code"].upper())
                if record:
                    self._try_upsert(record, kg_ok)
            course_list = ", ".join(c["code"] for c in courses)
            return (
                f"{semester} er courses: {course_list}. "
                f"(Courses offered in {semester}: {course_list}.)" + warning
            )

        return "Sorry, bujhte parini. (Sorry, I could not understand.)"

    def _kg_status(self) -> Tuple[bool, Optional[str]]:
        if self.kg is None:
            return False, "KG not configured"
        return self.kg.health()

    def _try_upsert(self, course: Dict, kg_ok: bool) -> None:
        if self.kg is None or not kg_ok:
            return
        self.kg.upsert_course(course)

    def _get_course(self, code: Optional[str]) -> Optional[Dict]:
        if not code:
            return None
        return self.by_code.get(code.upper())

    @staticmethod
    def _match_from_list(text_lower: str, candidates: List[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate.lower() in text_lower:
                return candidate
        return None
