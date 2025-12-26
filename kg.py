from typing import Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable


class KnowledgeGraph:
    def __init__(self, uri: str, user: str, password: str, database: Optional[str] = None):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = None

    def connect(self) -> None:
        if self.driver is None:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()
            self.driver = None

    def _session(self):
        if self.driver is None:
            self.connect()
        if self.database:
            return self.driver.session(database=self.database)
        return self.driver.session()

    def health(self) -> Tuple[bool, Optional[str]]:
        try:
            with self._session() as session:
                session.run("RETURN 1").consume()
            return True, None
        except Exception as exc:
            return False, str(exc)

    def ensure_constraints(self) -> Tuple[bool, Optional[str]]:
        statements = [
            "CREATE CONSTRAINT course_code_unique IF NOT EXISTS FOR (c:Course) REQUIRE c.code IS UNIQUE",
            "CREATE CONSTRAINT teacher_name_unique IF NOT EXISTS FOR (t:Teacher) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT department_name_unique IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT semester_name_unique IF NOT EXISTS FOR (s:Semester) REQUIRE s.name IS UNIQUE",
        ]
        try:
            with self._session() as session:
                for stmt in statements:
                    session.run(stmt).consume()
            return True, None
        except Exception as exc:
            return False, str(exc)

    def upsert_course(self, record: Dict) -> Tuple[bool, Optional[str]]:
        cypher = """
        MERGE (c:Course {code: $code})
        ON CREATE SET c.title = $title, c.credit = $credit
        ON MATCH SET c.title = $title, c.credit = $credit
        MERGE (t:Teacher {name: $teacher})
        MERGE (d:Department {name: $dept})
        MERGE (s:Semester {name: $semester})
        MERGE (c)-[:TAUGHT_BY]->(t)
        MERGE (c)-[:BELONGS_TO]->(d)
        MERGE (c)-[:OFFERED_IN]->(s)
        """
        params = {
            "code": record.get("course"),
            "title": record.get("title"),
            "credit": record.get("credit"),
            "teacher": record.get("teacher"),
            "dept": record.get("dept"),
            "semester": record.get("semester"),
        }
        try:
            with self._session() as session:
                session.run(cypher, params).consume()
            return True, None
        except Exception as exc:
            return False, str(exc)

    def summary(self) -> Tuple[Optional[Dict[str, int]], Optional[str]]:
        cypher = """
        MATCH (n)
        OPTIONAL MATCH ()-[r]->()
        RETURN count(DISTINCT n) AS nodes, count(r) AS rels
        """
        try:
            with self._session() as session:
                record = session.run(cypher).single()
                if record is None:
                    return {"nodes": 0, "edges": 0}, None
                return {"nodes": record["nodes"], "edges": record["rels"]}, None
        except Exception as exc:
            return None, str(exc)

    def export_graph(self) -> Tuple[Optional[Dict], Optional[str]]:
        try:
            with self._session() as session:
                node_rows = session.run(
                    "MATCH (n) RETURN id(n) AS id, labels(n)[0] AS label, properties(n) AS props"
                )
                nodes = [
                    {"id": row["id"], "type": row["label"], "props": row["props"]}
                    for row in node_rows
                ]
                edge_rows = session.run(
                    "MATCH (a)-[r]->(b) RETURN id(r) AS id, type(r) AS type, id(a) AS source, id(b) AS target"
                )
                edges = [
                    {
                        "id": row["id"],
                        "type": row["type"],
                        "source": row["source"],
                        "target": row["target"],
                    }
                    for row in edge_rows
                ]
            return {"nodes": nodes, "edges": edges}, None
        except Exception as exc:
            return None, str(exc)

    def get_courses_by_teacher(self, teacher: str) -> Tuple[List[Dict], Optional[str]]:
        cypher = """
        MATCH (t:Teacher {name: $teacher})<-[:TAUGHT_BY]-(c:Course)
        RETURN c.code AS code, c.title AS title
        ORDER BY c.code
        """
        try:
            with self._session() as session:
                rows = session.run(cypher, {"teacher": teacher})
                return [dict(row) for row in rows], None
        except Exception as exc:
            return [], str(exc)

    def get_courses_by_dept(self, dept: str) -> Tuple[List[Dict], Optional[str]]:
        cypher = """
        MATCH (d:Department {name: $dept})<-[:BELONGS_TO]-(c:Course)
        RETURN c.code AS code, c.title AS title
        ORDER BY c.code
        """
        try:
            with self._session() as session:
                rows = session.run(cypher, {"dept": dept})
                return [dict(row) for row in rows], None
        except Exception as exc:
            return [], str(exc)

    def get_courses_by_semester(self, semester: str) -> Tuple[List[Dict], Optional[str]]:
        cypher = """
        MATCH (s:Semester {name: $semester})<-[:OFFERED_IN]-(c:Course)
        RETURN c.code AS code, c.title AS title
        ORDER BY c.code
        """
        try:
            with self._session() as session:
                rows = session.run(cypher, {"semester": semester})
                return [dict(row) for row in rows], None
        except Exception as exc:
            return [], str(exc)
