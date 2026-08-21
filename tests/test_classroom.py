"""`gsuite classroom` — courses, rosters, coursework, submissions, posts.

Two things here are Classroom-specific and easy to get quietly wrong, so
they are pinned rather than assumed:

* a course is addressable by an *alias* (`d:school_math_101`), whose colon
  has to survive into the request line unencoded;
* every PATCH needs an `updateMask` naming exactly the fields being written,
  because Classroom *clears* any masked field the body omits.
"""
import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


COURSE = {
    "id": "123", "name": "Math 101", "section": "P1",
    "descriptionHeading": "Algebra", "description": "Intro algebra",
    "room": "301", "ownerId": "t1", "courseState": "ACTIVE",
    "enrollmentCode": "abc123", "creationTime": "2026-01-05T10:00:00Z",
    "updateTime": "2026-01-06T10:00:00Z",
    "alternateLink": "https://classroom.google.com/c/123",
}
STUDENT = {"courseId": "123", "userId": "s1", "profile": {
    "id": "s1", "name": {"fullName": "Ada Lovelace"},
    "emailAddress": "ada@school.edu"}}
TEACHER = {"courseId": "123", "userId": "t1", "profile": {
    "id": "t1", "name": {"fullName": "Alan Turing"},
    "emailAddress": "alan@school.edu"}}
WORK = {
    "courseId": "123", "id": "cw1", "title": "Problem set 1",
    "description": "Chapter 3", "state": "PUBLISHED", "maxPoints": 100,
    "workType": "ASSIGNMENT", "topicId": "tp1",
    "dueDate": {"year": 2026, "month": 5, "day": 4},
    "dueTime": {"hours": 17, "minutes": 30},
    "alternateLink": "https://classroom.google.com/c/123/a/cw1",
    "updateTime": "2026-01-06T10:00:00Z",
}
SUBMISSION = {
    "courseId": "123", "courseWorkId": "cw1", "id": "sub1", "userId": "s1",
    "state": "TURNED_IN", "late": True, "draftGrade": 80, "assignedGrade": 90,
    "alternateLink": "https://classroom.google.com/c/123/a/cw1/submissions/sub1",
    "updateTime": "2026-01-07T10:00:00Z",
}
ANNOUNCEMENT = {
    "courseId": "123", "id": "an1", "text": "No class Friday",
    "state": "PUBLISHED", "creatorUserId": "t1",
    "alternateLink": "https://classroom.google.com/c/123/p/an1",
    "updateTime": "2026-01-06T10:00:00Z",
}
TOPIC = {"courseId": "123", "topicId": "tp1", "name": "Unit 1",
         "updateTime": "2026-01-06T10:00:00Z"}


def _body(call):
    return json.loads(call["data"])


# -- courses -----------------------------------------------------------------

def test_courses_list_columns_and_url(svc):
    ft, run = svc
    ft.add("GET", "classroom.googleapis.com/v1/courses",
           {"courses": [COURSE, {**COURSE, "id": "124", "name": "Math 102"}]})
    out = run("classroom", "courses", "list")
    assert ft.calls[0]["url"].startswith(
        "https://classroom.googleapis.com/v1/courses")
    header = out.splitlines()[0]
    for column in ("ID", "NAME", "SECTION", "STATE"):
        assert column in header
    assert "Math 101" in out and "Math 102" in out and "ACTIVE" in out


def test_courses_list_filters_are_sent_as_query_params(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses", {"courses": []})
    run("classroom", "courses", "list", "--student", "s1", "--teacher", "me",
        "--state", "ARCHIVED")
    url = ft.calls[0]["url"]
    assert "studentId=s1" in url
    assert "teacherId=me" in url
    assert "courseStates=ARCHIVED" in url


def test_courses_list_sends_no_empty_filters(svc):
    """An unset filter must be absent, not sent as an empty string."""
    ft, run = svc
    ft.add("GET", "/v1/courses", {"courses": []})
    run("classroom", "courses", "list")
    url = ft.calls[0]["url"]
    assert "studentId" not in url and "teacherId" not in url
    assert "courseStates" not in url


def test_courses_get_emits_the_useful_fields(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123", COURSE)
    out = run("classroom", "courses", "get", "123")
    assert ft.calls[0]["url"] == "https://classroom.googleapis.com/v1/courses/123"
    assert "id: 123" in out
    assert "name: Math 101" in out
    assert "state: ACTIVE" in out
    assert "enrollmentCode: abc123" in out
    assert "link: https://classroom.google.com/c/123" in out


def test_courses_create_defaults_the_owner_to_the_caller(svc):
    ft, run = svc
    ft.add("POST", "/v1/courses", COURSE)
    out = run("classroom", "courses", "create", "--name", "Math 101",
              "--section", "P1")
    assert _body(ft.calls[0]) == {"name": "Math 101", "section": "P1",
                                  "ownerId": "me"}
    assert "created 123 Math 101" in out


def test_courses_create_passes_an_explicit_owner(svc):
    ft, run = svc
    ft.add("POST", "/v1/courses", COURSE)
    run("classroom", "courses", "create", "--name", "Math 101",
        "--owner", "t1@school.edu", "--room", "301", "--state", "ACTIVE")
    assert _body(ft.calls[0]) == {"name": "Math 101", "ownerId": "t1@school.edu",
                                  "room": "301", "courseState": "ACTIVE"}


def test_courses_update_masks_only_what_was_passed(svc):
    ft, run = svc
    ft.add("PATCH", "/v1/courses/123", COURSE)
    out = run("classroom", "courses", "update", "123", "--name", "Algebra I",
              "--room", "302")
    url = ft.calls[0]["url"]
    assert "updateMask=name%2Croom" in url
    assert _body(ft.calls[0]) == {"name": "Algebra I", "room": "302"}
    assert "updated 123" in out


def test_courses_update_mask_omits_untouched_fields(svc):
    """The mask is the whole safety property: a masked field the body omits
    is *cleared*, so a hardcoded list would wipe the description."""
    ft, run = svc
    ft.add("PATCH", "/v1/courses/123", COURSE)
    run("classroom", "courses", "update", "123", "--section", "P2")
    url = ft.calls[0]["url"]
    assert "updateMask=section" in url
    assert "description" not in url
    assert _body(ft.calls[0]) == {"section": "P2"}


def test_courses_update_with_no_flags_errors(svc):
    ft, run = svc
    run("classroom", "courses", "update", "123", expect=1)
    assert ft.calls == []


def test_courses_archive_and_unarchive_patch_the_state(svc):
    ft, run = svc
    ft.add("PATCH", "/v1/courses/123", COURSE)
    out = run("classroom", "courses", "archive", "123")
    assert "updateMask=courseState" in ft.calls[0]["url"]
    assert _body(ft.calls[0]) == {"courseState": "ARCHIVED"}
    assert "archived 123" in out
    ft.add("PATCH", "/v1/courses/123", COURSE)
    out = run("classroom", "courses", "unarchive", "123")
    assert _body(ft.calls[1]) == {"courseState": "ACTIVE"}
    assert "unarchived 123" in out


def test_courses_delete(svc):
    ft, run = svc
    ft.add("DELETE", "/v1/courses/123", {})
    out = run("classroom", "courses", "delete", "123")
    assert ft.calls[0]["method"] == "DELETE"
    assert "deleted 123" in out


# -- course identifiers: the alias colon, and everything else ----------------

def test_a_course_alias_keeps_its_colon_on_the_wire(svc):
    """`d:school_math_101` is a documented course id, not an escape hatch.

    Percent-encoding the colon would send `courses/d%3Aschool_math_101`,
    which is a different path than the one Classroom routes aliases on.
    """
    ft, run = svc
    ft.add("GET", "/v1/courses/d:school_math_101", COURSE)
    run("classroom", "courses", "get", "d:school_math_101")
    assert ft.calls[0]["url"] == (
        "https://classroom.googleapis.com/v1/courses/d:school_math_101")


def test_a_course_alias_works_for_nested_resources_too(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/d:school_math_101/students", {"students": []})
    run("classroom", "students", "list", "d:school_math_101")
    assert ft.calls[0]["url"].startswith(
        "https://classroom.googleapis.com/v1/courses/"
        "d:school_math_101/students")


def test_a_course_id_is_confined_to_one_path_segment(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/", COURSE)
    run("classroom", "courses", "get", "../../v1/other")
    assert ft.calls[0]["url"] == ("https://classroom.googleapis.com/v1/"
                                  "courses/..%2F..%2Fv1%2Fother")


def test_a_course_id_holding_url_punctuation_is_encoded(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/", COURSE)
    run("classroom", "courses", "get", "c?x=1#f")
    assert ft.calls[0]["url"] == ("https://classroom.googleapis.com/v1/"
                                  "courses/c%3Fx%3D1%23f")


@pytest.mark.parametrize("bad", ["", ".", ".."])
def test_a_traversal_or_empty_course_id_never_reaches_the_network(svc, bad):
    """`courses/..` resolves to a different endpoint than the one named, and
    `courses//students` to neither — refuse both before dialling out."""
    ft, run = svc
    run("classroom", "courses", "get", bad, expect=1)
    assert ft.calls == []


@pytest.mark.parametrize("argv", [
    ("coursework", "get", "123", ".."),
    ("coursework", "get", "123", ""),
    ("students", "get", "123", ".."),
    ("topics", "delete", "123", "."),
    ("submissions", "get", "123", "cw1", ".."),
])
def test_a_dotted_or_empty_id_is_refused_wherever_it_appears(svc, argv):
    """Percent-encoding cannot save these: `.` and `..` are unreserved, so
    they pass through `quote` untouched and `courseWork/..` addresses the
    course instead of the assignment. An empty segment does the same.
    """
    ft, run = svc
    run("classroom", *argv, expect=1)
    assert ft.calls == []


def test_a_colon_in_a_non_course_id_is_encoded(svc):
    """Only course ids have an alias form; elsewhere a colon is an attempt to
    reach a custom method (`…/sub1:return`), so it must not survive."""
    ft, run = svc
    ft.add("GET", "/v1/courses/123/courseWork/", WORK)
    run("classroom", "coursework", "get", "123", "cw1:return")
    assert ft.calls[0]["url"] == ("https://classroom.googleapis.com/v1/"
                                  "courses/123/courseWork/cw1%3Areturn")


# -- rosters -----------------------------------------------------------------

def test_students_list_flattens_the_profile(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/students", {"students": [STUDENT]})
    out = run("classroom", "students", "list", "123")
    header = out.splitlines()[0]
    for column in ("ID", "NAME", "EMAIL"):
        assert column in header
    assert "s1" in out and "Ada Lovelace" in out and "ada@school.edu" in out


def test_students_list_tolerates_a_hidden_profile(svc):
    """Without the profile scopes Classroom returns the id and nothing else."""
    ft, run = svc
    ft.add("GET", "/v1/courses/123/students",
           {"students": [{"courseId": "123", "userId": "s9"}]})
    out = run("classroom", "students", "list", "123")
    assert "s9" in out


def test_students_get(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/students/s1", STUDENT)
    out = run("classroom", "students", "get", "123", "s1")
    assert ft.calls[0]["url"] == ("https://classroom.googleapis.com/v1/"
                                  "courses/123/students/s1")
    assert "name: Ada Lovelace" in out
    assert "email: ada@school.edu" in out


def test_students_get_encodes_an_email_as_the_user_id(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/students/", STUDENT)
    run("classroom", "students", "get", "123", "ada@school.edu")
    assert ft.calls[0]["url"].endswith("/students/ada%40school.edu")


def test_students_add_posts_the_user_id(svc):
    ft, run = svc
    ft.add("POST", "/v1/courses/123/students", STUDENT)
    out = run("classroom", "students", "add", "123", "ada@school.edu")
    assert _body(ft.calls[0]) == {"userId": "ada@school.edu"}
    assert "added ada@school.edu to 123" in out


def test_students_add_passes_an_enrollment_code(svc):
    ft, run = svc
    ft.add("POST", "/v1/courses/123/students", STUDENT)
    run("classroom", "students", "add", "123", "s1", "--enrollment-code", "abc")
    assert "enrollmentCode=abc" in ft.calls[0]["url"]


def test_students_remove(svc):
    ft, run = svc
    ft.add("DELETE", "/v1/courses/123/students/s1", {})
    out = run("classroom", "students", "remove", "123", "s1")
    assert ft.calls[0]["method"] == "DELETE"
    assert "removed s1 from 123" in out


def test_teachers_round_trip(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/teachers", {"teachers": [TEACHER]})
    ft.add("GET", "/v1/courses/123/teachers/t1", TEACHER)
    ft.add("POST", "/v1/courses/123/teachers", TEACHER)
    ft.add("DELETE", "/v1/courses/123/teachers/t1", {})
    assert "Alan Turing" in run("classroom", "teachers", "list", "123")
    assert "email: alan@school.edu" in run("classroom", "teachers", "get",
                                           "123", "t1")
    assert "added t1 to 123" in run("classroom", "teachers", "add", "123", "t1")
    assert "removed t1 from 123" in run("classroom", "teachers", "remove",
                                        "123", "t1")
    assert _body(ft.calls[2]) == {"userId": "t1"}


# -- coursework --------------------------------------------------------------

def test_coursework_list_uses_the_courseWork_key(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/courseWork", {"courseWork": [WORK]})
    out = run("classroom", "coursework", "list", "123")
    header = out.splitlines()[0]
    for column in ("ID", "TITLE", "STATE", "DUE", "POINTS"):
        assert column in header
    assert "Problem set 1" in out and "100" in out


def test_coursework_list_renders_due_date_and_time_together(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/courseWork", {"courseWork": [
        WORK,
        {**WORK, "id": "cw2", "dueTime": None},
        {**WORK, "id": "cw3", "dueDate": None, "dueTime": None},
    ]})
    out = run("--csv", "classroom", "coursework", "list", "123")
    rows = out.splitlines()
    assert "2026-05-04 17:30" in rows[1]
    assert rows[2].split(",")[3] == "2026-05-04"
    assert rows[3].split(",")[3] == ""


def test_coursework_list_filters_by_state(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/courseWork", {"courseWork": []})
    run("classroom", "coursework", "list", "123", "--state", "DRAFT")
    assert "courseWorkStates=DRAFT" in ft.calls[0]["url"]


def test_coursework_get(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/courseWork/cw1", WORK)
    out = run("classroom", "coursework", "get", "123", "cw1")
    assert "title: Problem set 1" in out
    assert "points: 100" in out
    assert "due: 2026-05-04 17:30" in out
    assert "topic: tp1" in out


def test_coursework_create_splits_the_due_date_into_classrooms_shape(svc):
    ft, run = svc
    ft.add("POST", "/v1/courses/123/courseWork", WORK)
    out = run("classroom", "coursework", "create", "123",
              "--title", "Problem set 1", "--due", "2026-05-04",
              "--due-time", "17:30", "--points", "100")
    assert _body(ft.calls[0]) == {
        "title": "Problem set 1",
        "workType": "ASSIGNMENT",
        "state": "PUBLISHED",
        "dueDate": {"year": 2026, "month": 5, "day": 4},
        "dueTime": {"hours": 17, "minutes": 30},
        "maxPoints": 100.0,
    }
    assert "created cw1 Problem set 1" in out


def test_coursework_create_rejects_a_bad_due_date(svc):
    ft, run = svc
    run("classroom", "coursework", "create", "123", "--title", "x",
        "--due", "next friday", expect=1)
    assert ft.calls == []


def test_coursework_create_rejects_a_bad_due_time(svc):
    ft, run = svc
    run("classroom", "coursework", "create", "123", "--title", "x",
        "--due", "2026-05-04", "--due-time", "half five", expect=1)
    assert ft.calls == []


def test_coursework_create_refuses_a_time_without_a_date(svc):
    """Classroom rejects a dueTime with no dueDate; say so before the round
    trip, in terms of the flags the user actually typed."""
    ft, run = svc
    run("classroom", "coursework", "create", "123", "--title", "x",
        "--due-time", "17:30", expect=1)
    assert ft.calls == []


def test_coursework_update_masks_only_what_was_passed(svc):
    ft, run = svc
    ft.add("PATCH", "/v1/courses/123/courseWork/cw1", WORK)
    out = run("classroom", "coursework", "update", "123", "cw1",
              "--title", "Problem set 2", "--due", "2026-06-01")
    url = ft.calls[0]["url"]
    assert "updateMask=title%2CdueDate" in url
    assert _body(ft.calls[0]) == {
        "title": "Problem set 2",
        "dueDate": {"year": 2026, "month": 6, "day": 1}}
    assert "updated cw1" in out


def test_coursework_update_with_no_flags_errors(svc):
    ft, run = svc
    run("classroom", "coursework", "update", "123", "cw1", expect=1)
    assert ft.calls == []


def test_coursework_delete(svc):
    ft, run = svc
    ft.add("DELETE", "/v1/courses/123/courseWork/cw1", {})
    out = run("classroom", "coursework", "delete", "123", "cw1")
    assert ft.calls[0]["method"] == "DELETE"
    assert "deleted cw1" in out


# -- student submissions -----------------------------------------------------

def test_submissions_list_spans_all_coursework_by_default(svc):
    """`-` is Classroom's own wildcard for courseWorkId, and it is the only
    way to ask "what is outstanding in this course?" in one call."""
    ft, run = svc
    ft.add("GET", "/v1/courses/123/courseWork/-/studentSubmissions",
           {"studentSubmissions": [SUBMISSION]})
    out = run("classroom", "submissions", "list", "123")
    assert ft.calls[0]["url"].startswith(
        "https://classroom.googleapis.com/v1/courses/123/courseWork/-/"
        "studentSubmissions")
    header = out.splitlines()[0]
    for column in ("ID", "COURSEWORK", "USER", "STATE", "GRADE", "LATE"):
        assert column in header
    assert "sub1" in out and "TURNED_IN" in out and "90" in out


def test_submissions_list_narrows_by_coursework_user_and_state(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/courseWork/cw1/studentSubmissions",
           {"studentSubmissions": []})
    run("classroom", "submissions", "list", "123", "--coursework", "cw1",
        "--user", "s1", "--state", "TURNED_IN", "--late", "LATE_ONLY")
    url = ft.calls[0]["url"]
    assert "/courseWork/cw1/studentSubmissions" in url
    assert "userId=s1" in url
    assert "states=TURNED_IN" in url
    assert "late=LATE_ONLY" in url


def test_submissions_list_marks_late_work(svc):
    ft, run = svc
    ft.add("GET", "/studentSubmissions", {"studentSubmissions": [
        SUBMISSION, {**SUBMISSION, "id": "sub2", "late": False}]})
    out = run("--csv", "classroom", "submissions", "list", "123")
    rows = out.splitlines()
    assert rows[1].endswith(",yes")
    assert rows[2].endswith(",")


def test_submissions_get(svc):
    ft, run = svc
    ft.add("GET", "/courseWork/cw1/studentSubmissions/sub1", SUBMISSION)
    out = run("classroom", "submissions", "get", "123", "cw1", "sub1")
    assert ft.calls[0]["url"] == (
        "https://classroom.googleapis.com/v1/courses/123/courseWork/cw1/"
        "studentSubmissions/sub1")
    assert "user: s1" in out
    assert "state: TURNED_IN" in out
    assert "assignedGrade: 90" in out
    assert "draftGrade: 80" in out


def test_submissions_grade_masks_the_grades_actually_given(svc):
    ft, run = svc
    ft.add("PATCH", "/studentSubmissions/sub1", SUBMISSION)
    out = run("classroom", "submissions", "grade", "123", "cw1", "sub1",
              "--grade", "90")
    url = ft.calls[0]["url"]
    assert "updateMask=assignedGrade" in url
    assert "draftGrade" not in url
    assert _body(ft.calls[0]) == {"assignedGrade": 90.0}
    assert "graded sub1" in out


def test_submissions_grade_can_set_a_draft_grade_only(svc):
    ft, run = svc
    ft.add("PATCH", "/studentSubmissions/sub1", SUBMISSION)
    run("classroom", "submissions", "grade", "123", "cw1", "sub1",
        "--draft-grade", "75")
    assert "updateMask=draftGrade" in ft.calls[0]["url"]
    assert _body(ft.calls[0]) == {"draftGrade": 75.0}


def test_submissions_grade_needs_a_grade(svc):
    ft, run = svc
    run("classroom", "submissions", "grade", "123", "cw1", "sub1", expect=1)
    assert ft.calls == []


@pytest.mark.parametrize("command,method,word", [
    ("return", "return", "returned"),
    ("turn-in", "turnIn", "turned in"),
    ("reclaim", "reclaim", "reclaimed"),
])
def test_submissions_lifecycle_verbs_post_to_a_custom_method(svc, command,
                                                             method, word):
    ft, run = svc
    ft.add("POST", f"/studentSubmissions/sub1:{method}", {})
    out = run("classroom", "submissions", command, "123", "cw1", "sub1")
    assert ft.calls[0]["url"] == (
        "https://classroom.googleapis.com/v1/courses/123/courseWork/cw1/"
        f"studentSubmissions/sub1:{method}")
    assert f"{word} sub1" in out


# -- announcements -----------------------------------------------------------

def test_announcements_list(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/announcements",
           {"announcements": [ANNOUNCEMENT]})
    out = run("classroom", "announcements", "list", "123")
    header = out.splitlines()[0]
    for column in ("ID", "TEXT", "STATE", "UPDATED"):
        assert column in header
    assert "No class Friday" in out


def test_announcements_list_keeps_a_multiline_post_on_one_row(svc):
    """Announcement bodies are prose, newlines included; a raw cell would
    shear the table apart at the first line break."""
    ft, run = svc
    ft.add("GET", "/v1/courses/123/announcements", {"announcements": [
        {**ANNOUNCEMENT, "text": "Reminder:\n\n  bring a calculator"}]})
    out = run("classroom", "announcements", "list", "123")
    assert len(out.splitlines()) == 2
    assert "Reminder: bring a calculator" in out


def test_announcements_list_filters_by_state(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/announcements", {"announcements": []})
    run("classroom", "announcements", "list", "123", "--state", "DRAFT")
    assert "announcementStates=DRAFT" in ft.calls[0]["url"]


def test_announcements_get_shows_the_whole_text(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/announcements/an1", ANNOUNCEMENT)
    out = run("classroom", "announcements", "get", "123", "an1")
    assert "id: an1" in out
    assert "text: No class Friday" in out
    assert "state: PUBLISHED" in out


def test_announcements_create(svc):
    ft, run = svc
    ft.add("POST", "/v1/courses/123/announcements", ANNOUNCEMENT)
    out = run("classroom", "announcements", "create", "123",
              "--text", "No class Friday")
    assert _body(ft.calls[0]) == {"text": "No class Friday",
                                  "state": "PUBLISHED"}
    assert "created an1" in out


def test_announcements_update_masks_only_what_was_passed(svc):
    ft, run = svc
    ft.add("PATCH", "/v1/courses/123/announcements/an1", ANNOUNCEMENT)
    out = run("classroom", "announcements", "update", "123", "an1",
              "--text", "No class Monday")
    assert "updateMask=text" in ft.calls[0]["url"]
    assert _body(ft.calls[0]) == {"text": "No class Monday"}
    assert "updated an1" in out


def test_announcements_update_with_no_flags_errors(svc):
    ft, run = svc
    run("classroom", "announcements", "update", "123", "an1", expect=1)
    assert ft.calls == []


def test_announcements_delete(svc):
    ft, run = svc
    ft.add("DELETE", "/v1/courses/123/announcements/an1", {})
    out = run("classroom", "announcements", "delete", "123", "an1")
    assert ft.calls[0]["method"] == "DELETE"
    assert "deleted an1" in out


# -- topics ------------------------------------------------------------------

def test_topics_list_reads_the_singular_topic_key(svc):
    """Classroom's ListTopicResponse names its array `topic`, not `topics` —
    reading the plural would silently print an empty table forever."""
    ft, run = svc
    ft.add("GET", "/v1/courses/123/topics", {"topic": [TOPIC]})
    out = run("classroom", "topics", "list", "123")
    header = out.splitlines()[0]
    for column in ("ID", "NAME", "UPDATED"):
        assert column in header
    assert "tp1" in out and "Unit 1" in out


def test_topics_get(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses/123/topics/tp1", TOPIC)
    out = run("classroom", "topics", "get", "123", "tp1")
    assert "id: tp1" in out
    assert "name: Unit 1" in out


def test_topics_create(svc):
    ft, run = svc
    ft.add("POST", "/v1/courses/123/topics", TOPIC)
    out = run("classroom", "topics", "create", "123", "--name", "Unit 1")
    assert _body(ft.calls[0]) == {"name": "Unit 1"}
    assert "created tp1 Unit 1" in out


def test_topics_update(svc):
    ft, run = svc
    ft.add("PATCH", "/v1/courses/123/topics/tp1", TOPIC)
    out = run("classroom", "topics", "update", "123", "tp1", "--name", "Unit 2")
    assert "updateMask=name" in ft.calls[0]["url"]
    assert _body(ft.calls[0]) == {"name": "Unit 2"}
    assert "updated tp1" in out


def test_topics_delete(svc):
    ft, run = svc
    ft.add("DELETE", "/v1/courses/123/topics/tp1", {})
    out = run("classroom", "topics", "delete", "123", "tp1")
    assert ft.calls[0]["method"] == "DELETE"
    assert "deleted tp1" in out


# -- output flags and registration -------------------------------------------

def test_json_output_carries_the_raw_rows(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses", {"courses": [COURSE]})
    rows = json.loads(run("--json", "classroom", "courses", "list"))
    assert rows[0]["id"] == "123" and rows[0]["name"] == "Math 101"


def test_fields_selects_columns(svc):
    ft, run = svc
    ft.add("GET", "/v1/courses", {"courses": [COURSE]})
    out = run("--fields", "NAME", "classroom", "courses", "list")
    assert out.splitlines()[0].strip() == "NAME"
    assert "Math 101" in out


def test_readonly_refuses_a_classroom_mutation(svc):
    ft, run = svc
    run("--readonly", "classroom", "courses", "delete", "123", expect=1)
    assert ft.calls == []


def test_classroom_is_registered():
    from gsuite.cli import SERVICE_MODULES

    assert "classroom" in SERVICE_MODULES


def test_classroom_scopes_registered():
    from gsuite.oauth import SERVICE_SCOPES, scopes_for

    assert SERVICE_SCOPES["classroom"] == [
        "https://www.googleapis.com/auth/classroom.announcements",
        "https://www.googleapis.com/auth/classroom.courses",
        "https://www.googleapis.com/auth/classroom.coursework.me",
        "https://www.googleapis.com/auth/classroom.coursework.students",
        "https://www.googleapis.com/auth/classroom.profile.emails",
        "https://www.googleapis.com/auth/classroom.rosters",
        "https://www.googleapis.com/auth/classroom.topics",
    ]
    # and it is reachable through the flag users actually type
    assert ("https://www.googleapis.com/auth/classroom.rosters"
            in scopes_for(["classroom"]))


def test_a_classroom_scope_error_names_the_service_to_reauthorize():
    """The 403 hint is only useful if it can map the host back to a service."""
    from gsuite.api import service_for_url

    assert service_for_url(
        "https://classroom.googleapis.com/v1/courses") == "classroom"
