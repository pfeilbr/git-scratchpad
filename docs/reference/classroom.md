# gsuite classroom

Google Classroom: courses, rosters, coursework.

```text
usage: gsuite classroom [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite classroom courses`

Manage courses.

#### `gsuite classroom courses list`

List courses.

```text
usage: gsuite classroom courses list [-h] [--student ID] [--teacher ID]
                                     [--state {ACTIVE,ARCHIVED,PROVISIONED,DECLINED,SUSPENDED}]
                                     [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--student ID` |  |  | only courses this user takes (`me` for yourself) |
| `--teacher ID` |  |  | only courses this user teaches |
| `--state {ACTIVE,ARCHIVED,PROVISIONED,DECLINED,SUSPENDED}` |  |  |  |
| `--max MAX` |  | `100` | maximum results (default: 100) |

#### `gsuite classroom courses get`

Show a course.

```text
usage: gsuite classroom courses get [-h] course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |

#### `gsuite classroom courses create`

Create a course.

```text
usage: gsuite classroom courses create [-h] --name NAME [--section SECTION]
                                       [--description DESCRIPTION]
                                       [--description-heading DESCRIPTION_HEADING]
                                       [--room ROOM] [--owner OWNER]
                                       [--state {ACTIVE,ARCHIVED,PROVISIONED,DECLINED,SUSPENDED}]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--name NAME` | yes |  |  |
| `--section SECTION` |  |  |  |
| `--description DESCRIPTION` |  |  |  |
| `--description-heading DESCRIPTION_HEADING` |  |  |  |
| `--room ROOM` |  |  |  |
| `--owner OWNER` |  | `me` | course owner (default: me) |
| `--state {ACTIVE,ARCHIVED,PROVISIONED,DECLINED,SUSPENDED}` |  |  |  |

#### `gsuite classroom courses update`

Change a course's details.

```text
usage: gsuite classroom courses update [-h] [--name NAME] [--section SECTION]
                                       [--description DESCRIPTION]
                                       [--description-heading DESCRIPTION_HEADING]
                                       [--room ROOM] [--owner OWNER]
                                       [--state {ACTIVE,ARCHIVED,PROVISIONED,DECLINED,SUSPENDED}]
                                       course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--name NAME` |  |  |  |
| `--section SECTION` |  |  |  |
| `--description DESCRIPTION` |  |  |  |
| `--description-heading DESCRIPTION_HEADING` |  |  |  |
| `--room ROOM` |  |  |  |
| `--owner OWNER` |  |  |  |
| `--state {ACTIVE,ARCHIVED,PROVISIONED,DECLINED,SUSPENDED}` |  |  |  |

#### `gsuite classroom courses archive`

Archive a course.

```text
usage: gsuite classroom courses archive [-h] course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |

#### `gsuite classroom courses unarchive`

Return an archived course to active.

```text
usage: gsuite classroom courses unarchive [-h] course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |

#### `gsuite classroom courses delete`

Delete a course (it must be archived first).

```text
usage: gsuite classroom courses delete [-h] course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |

### `gsuite classroom students`

Manage the student roster.

#### `gsuite classroom students list`

List a course's students.

```text
usage: gsuite classroom students list [-h] [--max MAX] course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--max MAX` |  | `100` | maximum results (default: 100) |

#### `gsuite classroom students get`

Show one student.

```text
usage: gsuite classroom students get [-h] course user
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `user` | yes |  | user id, email address, or `me` |

#### `gsuite classroom students add`

Enroll a student.

```text
usage: gsuite classroom students add [-h] [--enrollment-code ENROLLMENT_CODE]
                                     course user
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `user` | yes |  | user id, email address, or `me` |
| `--enrollment-code ENROLLMENT_CODE` |  |  | the course's enrollment code, when joining one you were not invited to |

#### `gsuite classroom students remove`

Unenroll a student.

```text
usage: gsuite classroom students remove [-h] course user
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `user` | yes |  | user id, email address, or `me` |

### `gsuite classroom teachers`

Manage the teacher roster.

#### `gsuite classroom teachers list`

List a course's teachers.

```text
usage: gsuite classroom teachers list [-h] [--max MAX] course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--max MAX` |  | `50` | maximum results (default: 50) |

#### `gsuite classroom teachers get`

Show one teacher.

```text
usage: gsuite classroom teachers get [-h] course user
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `user` | yes |  | user id, email address, or `me` |

#### `gsuite classroom teachers add`

Add a co-teacher.

```text
usage: gsuite classroom teachers add [-h] course user
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `user` | yes |  | user id, email address, or `me` |

#### `gsuite classroom teachers remove`

Remove a teacher.

```text
usage: gsuite classroom teachers remove [-h] course user
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `user` | yes |  | user id, email address, or `me` |

### `gsuite classroom coursework`

Assignments and questions.

#### `gsuite classroom coursework list`

List a course's coursework.

```text
usage: gsuite classroom coursework list [-h]
                                        [--state {PUBLISHED,DRAFT,DELETED}]
                                        [--max MAX]
                                        course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--state {PUBLISHED,DRAFT,DELETED}` |  |  |  |
| `--max MAX` |  | `50` | maximum results (default: 50) |

#### `gsuite classroom coursework get`

Show one piece of coursework.

```text
usage: gsuite classroom coursework get [-h] course coursework
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |

#### `gsuite classroom coursework create`

Create an assignment.

```text
usage: gsuite classroom coursework create [-h] --title TITLE
                                          [--description DESCRIPTION]
                                          [--due YYYY-MM-DD]
                                          [--due-time HH:MM] [--points POINTS]
                                          [--topic ID]
                                          [--type {ASSIGNMENT,SHORT_ANSWER_QUESTION,MULTIPLE_CHOICE_QUESTION}]
                                          [--state {PUBLISHED,DRAFT}]
                                          course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--title TITLE` | yes |  |  |
| `--description DESCRIPTION` |  |  |  |
| `--due YYYY-MM-DD` |  |  | due date |
| `--due-time HH:MM` |  |  | time of day the work is due, in UTC (needs --due) |
| `--points POINTS` |  |  | maximum points |
| `--topic ID` |  |  | topic id to file it under |
| `--type {ASSIGNMENT,SHORT_ANSWER_QUESTION,MULTIPLE_CHOICE_QUESTION}` |  | `ASSIGNMENT` |  |
| `--state {PUBLISHED,DRAFT}` |  | `PUBLISHED` | visibility on creation (default: PUBLISHED) |

#### `gsuite classroom coursework update`

Change coursework.

```text
usage: gsuite classroom coursework update [-h] [--title TITLE]
                                          [--description DESCRIPTION]
                                          [--due YYYY-MM-DD]
                                          [--due-time HH:MM] [--points POINTS]
                                          [--topic ID]
                                          [--state {PUBLISHED,DRAFT,DELETED}]
                                          course coursework
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |
| `--title TITLE` |  |  |  |
| `--description DESCRIPTION` |  |  |  |
| `--due YYYY-MM-DD` |  |  |  |
| `--due-time HH:MM` |  |  |  |
| `--points POINTS` |  |  |  |
| `--topic ID` |  |  |  |
| `--state {PUBLISHED,DRAFT,DELETED}` |  |  |  |

#### `gsuite classroom coursework delete`

Delete coursework.

```text
usage: gsuite classroom coursework delete [-h] course coursework
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |

### `gsuite classroom submissions`

Student submissions: grade, return, turn in.

#### `gsuite classroom submissions list`

List student submissions.

```text
usage: gsuite classroom submissions list [-h] [--coursework ID] [--user ID]
                                         [--state {NEW,CREATED,TURNED_IN,RETURNED,RECLAIMED_BY_STUDENT}]
                                         [--late {LATE_ONLY,NOT_LATE_ONLY}]
                                         [--max MAX]
                                         course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--coursework ID` |  | `-` | one assignment (default: all of them) |
| `--user ID` |  |  | only this student |
| `--state {NEW,CREATED,TURNED_IN,RETURNED,RECLAIMED_BY_STUDENT}` |  |  |  |
| `--late {LATE_ONLY,NOT_LATE_ONLY}` |  |  |  |
| `--max MAX` |  | `100` | maximum results (default: 100) |

#### `gsuite classroom submissions get`

Show one submission.

```text
usage: gsuite classroom submissions get [-h] course coursework submission
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |
| `submission` | yes |  | student submission id |

#### `gsuite classroom submissions grade`

Grade a submission.

```text
usage: gsuite classroom submissions grade [-h] [--grade GRADE]
                                          [--draft-grade DRAFT_GRADE]
                                          course coursework submission
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |
| `submission` | yes |  | student submission id |
| `--grade GRADE` |  |  | the grade the student sees once it is returned |
| `--draft-grade DRAFT_GRADE` |  |  | a working grade, visible only to teachers |

#### `gsuite classroom submissions return`

Return a submission to the student.

```text
usage: gsuite classroom submissions return [-h] course coursework submission
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |
| `submission` | yes |  | student submission id |

#### `gsuite classroom submissions turn-in`

Turn in your own submission.

```text
usage: gsuite classroom submissions turn-in [-h] course coursework submission
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |
| `submission` | yes |  | student submission id |

#### `gsuite classroom submissions reclaim`

Take back your own turned-in submission.

```text
usage: gsuite classroom submissions reclaim [-h] course coursework submission
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `coursework` | yes |  | coursework id |
| `submission` | yes |  | student submission id |

### `gsuite classroom announcements`

Post announcements to a class.

#### `gsuite classroom announcements list`

List announcements.

```text
usage: gsuite classroom announcements list [-h]
                                           [--state {PUBLISHED,DRAFT,DELETED}]
                                           [--max MAX]
                                           course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--state {PUBLISHED,DRAFT,DELETED}` |  |  |  |
| `--max MAX` |  | `25` | maximum results (default: 25) |

#### `gsuite classroom announcements get`

Show one announcement in full.

```text
usage: gsuite classroom announcements get [-h] course announcement
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `announcement` | yes |  | announcement id |

#### `gsuite classroom announcements create`

Post an announcement.

```text
usage: gsuite classroom announcements create [-h] --text TEXT
                                             [--state {PUBLISHED,DRAFT}]
                                             course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--text TEXT` | yes |  |  |
| `--state {PUBLISHED,DRAFT}` |  | `PUBLISHED` | visibility on creation (default: PUBLISHED) |

#### `gsuite classroom announcements update`

Edit an announcement.

```text
usage: gsuite classroom announcements update [-h] [--text TEXT]
                                             [--state {PUBLISHED,DRAFT,DELETED}]
                                             course announcement
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `announcement` | yes |  | announcement id |
| `--text TEXT` |  |  |  |
| `--state {PUBLISHED,DRAFT,DELETED}` |  |  |  |

#### `gsuite classroom announcements delete`

Delete an announcement.

```text
usage: gsuite classroom announcements delete [-h] course announcement
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `announcement` | yes |  | announcement id |

### `gsuite classroom topics`

Group coursework under topics.

#### `gsuite classroom topics list`

List a course's topics.

```text
usage: gsuite classroom topics list [-h] [--max MAX] course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--max MAX` |  | `50` | maximum results (default: 50) |

#### `gsuite classroom topics get`

Show one topic.

```text
usage: gsuite classroom topics get [-h] course topic
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `topic` | yes |  | topic id |

#### `gsuite classroom topics create`

Create a topic.

```text
usage: gsuite classroom topics create [-h] --name NAME course
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `--name NAME` | yes |  |  |

#### `gsuite classroom topics update`

Rename a topic.

```text
usage: gsuite classroom topics update [-h] [--name NAME] course topic
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `topic` | yes |  | topic id |
| `--name NAME` |  |  |  |

#### `gsuite classroom topics delete`

Delete a topic.

```text
usage: gsuite classroom topics delete [-h] course topic
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `course` | yes |  | course id, or an alias like d:school_math_101 |
| `topic` | yes |  | topic id |

## Examples

**What am I teaching, and who is in it?**

```console
$ gsuite classroom courses list --teacher me
$ gsuite classroom students list 123
ID   NAME       SECTION  STATE
123  Math 101   P1       ACTIVE
```

**Set an assignment, then see what came in**

```console
$ gsuite classroom coursework create 123 --title 'Problem set 1' --due 2026-05-04 --points 100
$ gsuite classroom submissions list 123 --coursework cw1
ID    COURSEWORK  USER  STATE      GRADE  LATE
sub1  cw1         s1    TURNED_IN  90     yes
```

**Grade a submission and hand it back**

```console
$ gsuite classroom submissions grade 123 cw1 sub1 --grade 90
$ gsuite classroom submissions return 123 cw1 sub1
returned sub1
```

**Courses answer to their alias as well as their id**

```console
$ gsuite classroom announcements create d:school_math_101 --text 'No class Friday'
created an1
```
