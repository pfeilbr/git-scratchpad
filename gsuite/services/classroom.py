"""`gsuite classroom` — courses, rosters, coursework, submissions, posts."""
from __future__ import annotations

import datetime as dt
import urllib.parse

from gsuite.api import Client
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://classroom.googleapis.com/v1"

COURSE_STATES = ["ACTIVE", "ARCHIVED", "PROVISIONED", "DECLINED", "SUSPENDED"]
POST_STATES = ["PUBLISHED", "DRAFT", "DELETED"]
WORK_TYPES = ["ASSIGNMENT", "SHORT_ANSWER_QUESTION", "MULTIPLE_CHOICE_QUESTION"]
SUBMISSION_STATES = ["NEW", "CREATED", "TURNED_IN", "RETURNED",
                     "RECLAIMED_BY_STUDENT"]

COURSE_ARG = arg("course", help="course id, or an alias like d:school_math_101")
USER_ARG = arg("user", help="user id, email address, or `me`")
WORK_ARG = arg("coursework", help="coursework id")
SUBMISSION_ARG = arg("submission", help="student submission id")

# Anything a teacher would post to a class is published unless asked
# otherwise. Classroom's own API default is DRAFT, which is the safer choice
# for a client that might be a half-finished form — but a command someone
# typed on purpose that then shows nothing to the class is worse than one
# that does what it says, and `--state DRAFT` is right there.
POST_STATE_FLAG = arg("--state", choices=["PUBLISHED", "DRAFT"],
                      default="PUBLISHED",
                      help="visibility on creation (default: PUBLISHED)")


def _segment(value: str, what: str, *, safe: str = "") -> str:
    """Escape one Classroom identifier for use as a URL path segment.

    Percent-encoding alone is not the whole job. `quote` leaves ``.`` and
    ``..`` untouched — both are unreserved characters — so an id of ``..``
    sails through it and ``courseWork/../`` addresses the *course* rather
    than the assignment the command named. Neither is a usable id, so both
    are refused, as is the empty one that would ask for ``students/``.
    """
    if not value:
        raise CLIError(f"{what} must not be empty")
    if value in (".", ".."):
        raise CLIError(f"invalid {what} {value!r}: "
                       "'.' and '..' do not name a resource")
    return urllib.parse.quote(value, safe=safe)


def course_path(course: str) -> str:
    """Escape a course identifier, keeping the colon that an alias needs.

    Classroom addresses a course two ways: by the numeric id it assigned, or
    by an *alias* — `d:school_math_101` for a domain-scoped one, `p:…` for a
    project-scoped one. That colon is why this cannot take the default
    ``safe=""`` every other id here uses: the alias would go out as
    ``d%3Aschool_math_101``, and Google's front end routes on the raw path —
    a colon is how it tells a custom method (``…/sub1:return``) apart from a
    resource id — so the encoded form is not the same request.

    Nothing else is spared. ``/`` in particular is encoded, because a course
    id is a single segment and encoding the separator is what stops a hostile
    value from choosing a different endpoint.
    """
    return _segment(course, "course id", safe=":")


def _course_url(course: str, suffix: str = "") -> str:
    return f"{BASE}/courses/{course_path(course)}{suffix}"


def _work_url(args, suffix: str = "") -> str:
    work = _segment(args.coursework, "coursework id")
    return _course_url(args.course, f"/courseWork/{work}{suffix}")


def _submission_url(args, suffix: str = "") -> str:
    submission = _segment(args.submission, "submission id")
    return _work_url(args, f"/studentSubmissions/{submission}{suffix}")


def _changes(args, fields) -> tuple[dict, list[str]]:
    """The request body and update mask for the flags the user actually passed.

    `fields` is a table of (flag dest, API field, converter). A flag that was
    not given is `None`, and contributes to neither half — which is the whole
    point: Classroom writes only the fields named in `updateMask`, and
    *clears* any it names that the body omits. A mask hardcoded to the
    command's full field list would therefore make `coursework update
    --title x` silently wipe the description and the due date.
    """
    body, mask = {}, []
    for dest, field, convert in fields:
        value = getattr(args, dest, None)
        if value is None:
            continue
        body[field] = convert(value)
        mask.append(field)
    return body, mask


def _patch(args, url: str, fields, hint: str) -> None:
    body, mask = _changes(args, fields)
    if not mask:
        raise CLIError(f"nothing to update (pass {hint})")
    Client.for_args(args).patch(url, params={"updateMask": ",".join(mask)},
                                json_body=body)


def _due_date(value: str) -> dict:
    """`--due 2026-05-04` as Classroom's split-out calendar date."""
    try:
        day = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise CLIError(f"bad due date: {value} (want YYYY-MM-DD)") from exc
    return {"year": day.year, "month": day.month, "day": day.day}


def _due_time(value: str) -> dict:
    """`--due-time 17:30` as Classroom's time of day.

    UTC, and the help text says so rather than guessing: unlike a calendar
    event, an assignment deadline has no timeZone field to carry a local one.
    """
    try:
        moment = dt.time.fromisoformat(value)
    except ValueError as exc:
        raise CLIError(f"bad due time: {value} (want HH:MM, UTC)") from exc
    return {"hours": moment.hour, "minutes": moment.minute}


def _due(work: dict) -> str:
    """An assignment's deadline as `2026-05-04 17:30`, or as much as it has.

    The zero-valued parts are read with defaults because Classroom omits
    them: a deadline at 17:00 arrives as `{"hours": 17}`, with `minutes`
    left out entirely, which is ordinary proto3 JSON and not a missing field.
    """
    date, time = work.get("dueDate") or {}, work.get("dueTime") or {}
    if not date:
        return ""
    day = (f"{date.get('year', 0):04d}-{date.get('month', 0):02d}-"
           f"{date.get('day', 0):02d}")
    if not time:
        return day
    return f"{day} {time.get('hours', 0):02d}:{time.get('minutes', 0):02d}"


def _one_line(value: str, limit: int = 60) -> str:
    """A prose field on a single table row: whitespace collapsed, truncated.

    Announcement bodies are written in a text box, so they carry newlines and
    runs of spaces as a matter of course. Printed raw they would shear the
    table apart at the first line break; `get` still shows the whole thing.
    """
    text = " ".join((value or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _profile(member: dict, *path: str) -> str:
    """A roster entry's profile field, or "" when the scopes hid it.

    A `students list` without `classroom.profile.emails` still returns every
    userId — just with the names and addresses stripped — so every profile
    read has to survive the field simply not being there.
    """
    value: dict = member.get("profile") or {}
    for key in path[:-1]:
        value = value.get(key) or {}
    return value.get(path[-1], "")


def _grade(submission: dict) -> str:
    """What the student would see, falling back to the teacher's draft."""
    for key in ("assignedGrade", "draftGrade"):
        if key in submission:
            return str(submission[key])
    return ""


MEMBER_COLUMNS = [("ID", "userId"),
                  ("NAME", lambda m: _profile(m, "name", "fullName")),
                  ("EMAIL", lambda m: _profile(m, "emailAddress"))]


def _emit_member(args, member: dict) -> int:
    emit_obj(args, {
        "id": member.get("userId"),
        "name": _profile(member, "name", "fullName"),
        "email": _profile(member, "emailAddress"),
        "course": member.get("courseId", ""),
    })
    return 0


# -- courses -------------------------------------------------------------------

def cmd_courses_list(args) -> int:
    params = {}
    if args.student:
        params["studentId"] = args.student
    if args.teacher:
        params["teacherId"] = args.teacher
    if args.state:
        params["courseStates"] = args.state
    emit_paged(args, f"{BASE}/courses",
               [("ID", "id"), ("NAME", "name"), ("SECTION", "section"),
                ("STATE", "courseState")],
               params=params, key="courses", limit=args.max)
    return 0


def cmd_courses_get(args) -> int:
    course = Client.for_args(args).get(_course_url(args.course))
    emit_obj(args, {
        "id": course.get("id"),
        "name": course.get("name"),
        "section": course.get("section", ""),
        "description": course.get("description", ""),
        "room": course.get("room", ""),
        "state": course.get("courseState", ""),
        "owner": course.get("ownerId", ""),
        "enrollmentCode": course.get("enrollmentCode", ""),
        "link": course.get("alternateLink", ""),
        "updated": course.get("updateTime", ""),
    })
    return 0


COURSE_FIELDS = (
    ("name", "name", str),
    ("section", "section", str),
    ("description_heading", "descriptionHeading", str),
    ("description", "description", str),
    ("room", "room", str),
    ("owner", "ownerId", str),
    ("state", "courseState", str),
)


def cmd_courses_create(args) -> int:
    body, _mask = _changes(args, COURSE_FIELDS)
    course = Client.for_args(args).post(f"{BASE}/courses", json_body=body)
    confirm("created", course.get("id"), course.get("name"))
    return 0


def cmd_courses_update(args) -> int:
    _patch(args, _course_url(args.course), COURSE_FIELDS,
           "--name, --section, --description, --description-heading, --room, "
           "--owner, or --state")
    confirm("updated", args.course)
    return 0


def _set_course_state(args, state: str, word: str) -> int:
    Client.for_args(args).patch(_course_url(args.course),
                                params={"updateMask": "courseState"},
                                json_body={"courseState": state})
    confirm(word, args.course)
    return 0


def cmd_courses_archive(args) -> int:
    return _set_course_state(args, "ARCHIVED", "archived")


def cmd_courses_unarchive(args) -> int:
    return _set_course_state(args, "ACTIVE", "unarchived")


def cmd_courses_delete(args) -> int:
    Client.for_args(args).delete(_course_url(args.course))
    confirm("deleted", args.course)
    return 0


# -- rosters -------------------------------------------------------------------

def _roster_url(args, kind: str, user: str | None = None) -> str:
    suffix = f"/{kind}" + (f"/{_segment(user, 'user id')}"
                           if user is not None else "")
    return _course_url(args.course, suffix)


def cmd_students_list(args) -> int:
    emit_paged(args, _roster_url(args, "students"), MEMBER_COLUMNS,
               key="students", limit=args.max)
    return 0


def cmd_students_get(args) -> int:
    return _emit_member(args, Client.for_args(args).get(
        _roster_url(args, "students", args.user)))


def cmd_students_add(args) -> int:
    # The enrollment code is what a *student* uses to join a course they were
    # not invited to; a teacher adding someone directly does not need one.
    params = ({"enrollmentCode": args.enrollment_code}
              if args.enrollment_code else None)
    Client.for_args(args).post(_roster_url(args, "students"), params=params,
                               json_body={"userId": args.user})
    confirm("added", args.user, "to", args.course)
    return 0


def cmd_students_remove(args) -> int:
    Client.for_args(args).delete(_roster_url(args, "students", args.user))
    confirm("removed", args.user, "from", args.course)
    return 0


def cmd_teachers_list(args) -> int:
    emit_paged(args, _roster_url(args, "teachers"), MEMBER_COLUMNS,
               key="teachers", limit=args.max)
    return 0


def cmd_teachers_get(args) -> int:
    return _emit_member(args, Client.for_args(args).get(
        _roster_url(args, "teachers", args.user)))


def cmd_teachers_add(args) -> int:
    Client.for_args(args).post(_roster_url(args, "teachers"),
                               json_body={"userId": args.user})
    confirm("added", args.user, "to", args.course)
    return 0


def cmd_teachers_remove(args) -> int:
    Client.for_args(args).delete(_roster_url(args, "teachers", args.user))
    confirm("removed", args.user, "from", args.course)
    return 0


# -- coursework ----------------------------------------------------------------

WORK_FIELDS = (
    ("title", "title", str),
    ("description", "description", str),
    ("state", "state", str),
    ("due", "dueDate", _due_date),
    ("due_time", "dueTime", _due_time),
    ("points", "maxPoints", float),
    ("topic", "topicId", str),
)
# workType is fixed when the assignment is created — Classroom will not patch
# it — so it belongs to `create` alone.
WORK_CREATE_FIELDS = WORK_FIELDS + (("type", "workType", str),)


def cmd_coursework_list(args) -> int:
    params = {"courseWorkStates": args.state} if args.state else {}
    emit_paged(args, _course_url(args.course, "/courseWork"),
               [("ID", "id"), ("TITLE", "title"), ("STATE", "state"),
                ("DUE", _due), ("POINTS", "maxPoints")],
               params=params, key="courseWork", limit=args.max)
    return 0


def cmd_coursework_get(args) -> int:
    work = Client.for_args(args).get(_work_url(args))
    emit_obj(args, {
        "id": work.get("id"),
        "title": work.get("title"),
        "description": work.get("description", ""),
        "state": work.get("state", ""),
        "type": work.get("workType", ""),
        "due": _due(work),
        "points": work.get("maxPoints", ""),
        "topic": work.get("topicId", ""),
        "link": work.get("alternateLink", ""),
        "updated": work.get("updateTime", ""),
    })
    return 0


def cmd_coursework_create(args) -> int:
    # Classroom rejects a dueTime with no dueDate, and does it with a message
    # about proto fields rather than about the two flags that caused it.
    if args.due_time and not args.due:
        raise CLIError("--due-time needs --due as well "
                       "(Classroom has no time-only deadline)")
    body, _mask = _changes(args, WORK_CREATE_FIELDS)
    work = Client.for_args(args).post(_course_url(args.course, "/courseWork"),
                                      json_body=body)
    confirm("created", work.get("id"), work.get("title"))
    return 0


def cmd_coursework_update(args) -> int:
    _patch(args, _work_url(args), WORK_FIELDS,
           "--title, --description, --state, --due, --due-time, --points, "
           "or --topic")
    confirm("updated", args.coursework)
    return 0


def cmd_coursework_delete(args) -> int:
    Client.for_args(args).delete(_work_url(args))
    confirm("deleted", args.coursework)
    return 0


# -- student submissions -------------------------------------------------------

def cmd_submissions_list(args) -> int:
    params = {}
    if args.user:
        params["userId"] = args.user
    if args.state:
        params["states"] = args.state
    if args.late:
        params["late"] = args.late
    emit_paged(args, _work_url(args, "/studentSubmissions"),
               [("ID", "id"), ("COURSEWORK", "courseWorkId"),
                ("USER", "userId"), ("STATE", "state"), ("GRADE", _grade),
                ("LATE", lambda s: "yes" if s.get("late") else "")],
               params=params, key="studentSubmissions", limit=args.max)
    return 0


def cmd_submissions_get(args) -> int:
    submission = Client.for_args(args).get(_submission_url(args))
    emit_obj(args, {
        "id": submission.get("id"),
        "coursework": submission.get("courseWorkId", ""),
        "user": submission.get("userId", ""),
        "state": submission.get("state", ""),
        "late": submission.get("late", False),
        "draftGrade": submission.get("draftGrade", ""),
        "assignedGrade": submission.get("assignedGrade", ""),
        "link": submission.get("alternateLink", ""),
        "updated": submission.get("updateTime", ""),
    })
    return 0


def cmd_submissions_grade(args) -> int:
    # draftGrade is the teacher's working figure; assignedGrade is the one the
    # student sees once the work is returned. Which of them `--grade` writes
    # is the difference between marking and publishing, so both are flags.
    _patch(args, _submission_url(args),
           (("grade", "assignedGrade", float),
            ("draft_grade", "draftGrade", float)),
           "--grade or --draft-grade")
    confirm("graded", args.submission)
    return 0


def _submission_action(args, method: str, word: str) -> int:
    Client.for_args(args).post(_submission_url(args, f":{method}"))
    confirm(word, args.submission)
    return 0


def cmd_submissions_return(args) -> int:
    return _submission_action(args, "return", "returned")


def cmd_submissions_turn_in(args) -> int:
    return _submission_action(args, "turnIn", "turned in")


def cmd_submissions_reclaim(args) -> int:
    return _submission_action(args, "reclaim", "reclaimed")


# -- announcements -------------------------------------------------------------

ANNOUNCEMENT_FIELDS = (("text", "text", str), ("state", "state", str))


def _announcement_url(args) -> str:
    announcement = _segment(args.announcement, "announcement id")
    return _course_url(args.course, f"/announcements/{announcement}")


def cmd_announcements_list(args) -> int:
    params = {"announcementStates": args.state} if args.state else {}
    emit_paged(args, _course_url(args.course, "/announcements"),
               [("ID", "id"), ("TEXT", lambda a: _one_line(a.get("text", ""))),
                ("STATE", "state"), ("UPDATED", "updateTime")],
               params=params, key="announcements", limit=args.max)
    return 0


def cmd_announcements_get(args) -> int:
    announcement = Client.for_args(args).get(_announcement_url(args))
    emit_obj(args, {
        "id": announcement.get("id"),
        "text": announcement.get("text", ""),
        "state": announcement.get("state", ""),
        "creator": announcement.get("creatorUserId", ""),
        "link": announcement.get("alternateLink", ""),
        "updated": announcement.get("updateTime", ""),
    })
    return 0


def cmd_announcements_create(args) -> int:
    body, _mask = _changes(args, ANNOUNCEMENT_FIELDS)
    announcement = Client.for_args(args).post(
        _course_url(args.course, "/announcements"), json_body=body)
    confirm("created", announcement.get("id"))
    return 0


def cmd_announcements_update(args) -> int:
    _patch(args, _announcement_url(args), ANNOUNCEMENT_FIELDS,
           "--text or --state")
    confirm("updated", args.announcement)
    return 0


def cmd_announcements_delete(args) -> int:
    Client.for_args(args).delete(_announcement_url(args))
    confirm("deleted", args.announcement)
    return 0


# -- topics --------------------------------------------------------------------

def _topic_url(args) -> str:
    return _course_url(args.course,
                       f"/topics/{_segment(args.topic, 'topic id')}")


def cmd_topics_list(args) -> int:
    # `topic`, singular: that is genuinely what ListTopicResponse names its
    # array. Reading the plural spelling every other Classroom list method
    # uses would print an empty table for a course full of topics.
    emit_paged(args, _course_url(args.course, "/topics"),
               [("ID", "topicId"), ("NAME", "name"), ("UPDATED", "updateTime")],
               key="topic", limit=args.max)
    return 0


def cmd_topics_get(args) -> int:
    topic = Client.for_args(args).get(_topic_url(args))
    emit_obj(args, {
        "id": topic.get("topicId"),
        "name": topic.get("name", ""),
        "course": topic.get("courseId", ""),
        "updated": topic.get("updateTime", ""),
    })
    return 0


def cmd_topics_create(args) -> int:
    topic = Client.for_args(args).post(_course_url(args.course, "/topics"),
                                       json_body={"name": args.name})
    confirm("created", topic.get("topicId"), topic.get("name"))
    return 0


def cmd_topics_update(args) -> int:
    _patch(args, _topic_url(args), (("name", "name", str),), "--name")
    confirm("updated", args.topic)
    return 0


def cmd_topics_delete(args) -> int:
    Client.for_args(args).delete(_topic_url(args))
    confirm("deleted", args.topic)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "classroom",
                     "Google Classroom: courses, rosters, coursework", [
        Group("courses", "manage courses", (
            Cmd("list", cmd_courses_list, "list courses",
                (arg("--student", metavar="ID",
                     help="only courses this user takes (`me` for yourself)"),
                 arg("--teacher", metavar="ID",
                     help="only courses this user teaches"),
                 arg("--state", choices=COURSE_STATES),
                 max_flag(100))),
            Cmd("get", cmd_courses_get, "show a course", (COURSE_ARG,)),
            Cmd("create", cmd_courses_create, "create a course",
                (arg("--name", required=True),
                 arg("--section"), arg("--description"),
                 arg("--description-heading"), arg("--room"),
                 arg("--owner", default="me",
                     help="course owner (default: me)"),
                 arg("--state", choices=COURSE_STATES))),
            Cmd("update", cmd_courses_update, "change a course's details",
                (COURSE_ARG, arg("--name"), arg("--section"),
                 arg("--description"), arg("--description-heading"),
                 arg("--room"), arg("--owner"),
                 arg("--state", choices=COURSE_STATES))),
            Cmd("archive", cmd_courses_archive, "archive a course",
                (COURSE_ARG,)),
            Cmd("unarchive", cmd_courses_unarchive,
                "return an archived course to active", (COURSE_ARG,)),
            Cmd("delete", cmd_courses_delete,
                "delete a course (it must be archived first)", (COURSE_ARG,)),
        )),
        Group("students", "manage the student roster", (
            Cmd("list", cmd_students_list, "list a course's students",
                (COURSE_ARG, max_flag(100))),
            Cmd("get", cmd_students_get, "show one student",
                (COURSE_ARG, USER_ARG)),
            Cmd("add", cmd_students_add, "enroll a student",
                (COURSE_ARG, USER_ARG,
                 arg("--enrollment-code",
                     help="the course's enrollment code, when joining one you "
                          "were not invited to"))),
            Cmd("remove", cmd_students_remove, "unenroll a student",
                (COURSE_ARG, USER_ARG)),
        )),
        Group("teachers", "manage the teacher roster", (
            Cmd("list", cmd_teachers_list, "list a course's teachers",
                (COURSE_ARG, max_flag(50))),
            Cmd("get", cmd_teachers_get, "show one teacher",
                (COURSE_ARG, USER_ARG)),
            Cmd("add", cmd_teachers_add, "add a co-teacher",
                (COURSE_ARG, USER_ARG)),
            Cmd("remove", cmd_teachers_remove, "remove a teacher",
                (COURSE_ARG, USER_ARG)),
        )),
        Group("coursework", "assignments and questions", (
            Cmd("list", cmd_coursework_list, "list a course's coursework",
                (COURSE_ARG, arg("--state", choices=POST_STATES),
                 max_flag(50))),
            Cmd("get", cmd_coursework_get, "show one piece of coursework",
                (COURSE_ARG, WORK_ARG)),
            Cmd("create", cmd_coursework_create, "create an assignment",
                (COURSE_ARG, arg("--title", required=True),
                 arg("--description"),
                 arg("--due", metavar="YYYY-MM-DD", help="due date"),
                 arg("--due-time", metavar="HH:MM",
                     help="time of day the work is due, in UTC "
                          "(needs --due)"),
                 arg("--points", type=float, help="maximum points"),
                 arg("--topic", metavar="ID", help="topic id to file it under"),
                 arg("--type", choices=WORK_TYPES, default="ASSIGNMENT"),
                 POST_STATE_FLAG)),
            Cmd("update", cmd_coursework_update, "change coursework",
                (COURSE_ARG, WORK_ARG, arg("--title"), arg("--description"),
                 arg("--due", metavar="YYYY-MM-DD"),
                 arg("--due-time", metavar="HH:MM"),
                 arg("--points", type=float), arg("--topic", metavar="ID"),
                 arg("--state", choices=POST_STATES))),
            Cmd("delete", cmd_coursework_delete, "delete coursework",
                (COURSE_ARG, WORK_ARG)),
        )),
        Group("submissions", "student submissions: grade, return, turn in", (
            Cmd("list", cmd_submissions_list, "list student submissions",
                (COURSE_ARG,
                 arg("--coursework", default="-", metavar="ID",
                     help="one assignment (default: all of them)"),
                 arg("--user", metavar="ID", help="only this student"),
                 arg("--state", choices=SUBMISSION_STATES),
                 arg("--late", choices=["LATE_ONLY", "NOT_LATE_ONLY"]),
                 max_flag(100))),
            Cmd("get", cmd_submissions_get, "show one submission",
                (COURSE_ARG, WORK_ARG, SUBMISSION_ARG)),
            Cmd("grade", cmd_submissions_grade, "grade a submission",
                (COURSE_ARG, WORK_ARG, SUBMISSION_ARG,
                 arg("--grade", type=float,
                     help="the grade the student sees once it is returned"),
                 arg("--draft-grade", type=float,
                     help="a working grade, visible only to teachers"))),
            Cmd("return", cmd_submissions_return,
                "return a submission to the student",
                (COURSE_ARG, WORK_ARG, SUBMISSION_ARG)),
            Cmd("turn-in", cmd_submissions_turn_in,
                "turn in your own submission",
                (COURSE_ARG, WORK_ARG, SUBMISSION_ARG)),
            Cmd("reclaim", cmd_submissions_reclaim,
                "take back your own turned-in submission",
                (COURSE_ARG, WORK_ARG, SUBMISSION_ARG)),
        )),
        Group("announcements", "post announcements to a class", (
            Cmd("list", cmd_announcements_list, "list announcements",
                (COURSE_ARG, arg("--state", choices=POST_STATES),
                 max_flag(25))),
            Cmd("get", cmd_announcements_get,
                "show one announcement in full",
                (COURSE_ARG, arg("announcement", help="announcement id"))),
            Cmd("create", cmd_announcements_create, "post an announcement",
                (COURSE_ARG, arg("--text", required=True), POST_STATE_FLAG)),
            Cmd("update", cmd_announcements_update, "edit an announcement",
                (COURSE_ARG, arg("announcement", help="announcement id"),
                 arg("--text"), arg("--state", choices=POST_STATES))),
            Cmd("delete", cmd_announcements_delete, "delete an announcement",
                (COURSE_ARG, arg("announcement", help="announcement id"))),
        )),
        Group("topics", "group coursework under topics", (
            Cmd("list", cmd_topics_list, "list a course's topics",
                (COURSE_ARG, max_flag(50))),
            Cmd("get", cmd_topics_get, "show one topic",
                (COURSE_ARG, arg("topic", help="topic id"))),
            Cmd("create", cmd_topics_create, "create a topic",
                (COURSE_ARG, arg("--name", required=True))),
            Cmd("update", cmd_topics_update, "rename a topic",
                (COURSE_ARG, arg("topic", help="topic id"),
                 arg("--name"))),
            Cmd("delete", cmd_topics_delete, "delete a topic",
                (COURSE_ARG, arg("topic", help="topic id"))),
        )),
    ])
