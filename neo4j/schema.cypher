CREATE CONSTRAINT course_code_unique IF NOT EXISTS
FOR (c:Course)
REQUIRE c.code IS UNIQUE;

CREATE CONSTRAINT teacher_name_unique IF NOT EXISTS
FOR (t:Teacher)
REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT department_name_unique IF NOT EXISTS
FOR (d:Department)
REQUIRE d.name IS UNIQUE;

CREATE CONSTRAINT semester_name_unique IF NOT EXISTS
FOR (s:Semester)
REQUIRE s.name IS UNIQUE;
