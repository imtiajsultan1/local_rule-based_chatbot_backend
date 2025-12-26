import os

from dotenv import load_dotenv

from chatbot import load_courses
from kg import KnowledgeGraph


def main() -> None:
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE")

    kg = KnowledgeGraph(uri, user, password, database)
    ok, error = kg.ensure_constraints()
    if not ok:
        print(f"Failed to apply constraints: {error}")

    courses = load_courses()
    success_count = 0
    for course in courses:
        ok, error = kg.upsert_course(course)
        if ok:
            success_count += 1
        else:
            print(f"Failed to upsert {course.get('course')}: {error}")

    print(f"Seeded {success_count} courses into Neo4j.")
    kg.close()


if __name__ == "__main__":
    main()
