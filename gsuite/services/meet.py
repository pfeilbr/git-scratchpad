"""`gsuite meet` — spaces, conference records, participants."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import confirm, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://meet.googleapis.com/v2"


def _space_name(space: str) -> str:
    return space if space.startswith("spaces/") else f"spaces/{space}"


def _record_name(record: str) -> str:
    return (record if record.startswith("conferenceRecords/")
            else f"conferenceRecords/{record}")


def _participant_user(participant: dict) -> str:
    for kind in ("signedinUser", "anonymousUser", "phoneUser"):
        display = participant.get(kind, {}).get("displayName")
        if display:
            return display
    return ""


def cmd_create(args) -> int:
    body = {"config": {"accessType": args.access}} if args.access else {}
    space = Client.for_args(args).post(f"{BASE}/spaces", json_body=body)
    confirm("created", space.get("name"), space.get("meetingUri"))
    return 0


def cmd_get(args) -> int:
    space = Client.for_args(args).get(f"{BASE}/{_space_name(args.space)}")
    emit_obj(args, {
        "name": space.get("name"),
        "code": space.get("meetingCode"),
        "uri": space.get("meetingUri"),
        "access": space.get("config", {}).get("accessType"),
        "active": space.get("activeConference", {}).get("conferenceRecord", ""),
    })
    return 0


def cmd_end(args) -> int:
    name = _space_name(args.space)
    Client.for_args(args).post(f"{BASE}/{name}:endActiveConference")
    confirm("ended active conference in", name)
    return 0


def cmd_conferences(args) -> int:
    emit_paged(args, f"{BASE}/conferenceRecords",
               [("NAME", "name"), ("START", "startTime"),
                ("END", "endTime"), ("SPACE", "space")],
               key="conferenceRecords", limit=args.max)
    return 0


def cmd_participants(args) -> int:
    emit_paged(args, f"{BASE}/{_record_name(args.record)}/participants",
               [("NAME", "name"), ("USER", _participant_user),
                ("JOINED", "earliestStartTime")],
               key="participants", limit=args.max)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "meet", "Google Meet spaces and conferences", [
        Cmd("create", cmd_create, "create a meeting space",
            (arg("--access", choices=["OPEN", "TRUSTED", "RESTRICTED"],
                 help="who can join without knocking"),)),
        Cmd("get", cmd_get, "show a meeting space",
            (arg("space", help="e.g. spaces/abc or abc"),)),
        Cmd("end", cmd_end, "end the active conference in a space",
            (arg("space", help="e.g. spaces/abc or abc"),)),
        Cmd("conferences", cmd_conferences, "list past/ongoing conference records",
            (max_flag(25),)),
        Cmd("participants", cmd_participants,
            "list participants of a conference record",
            (arg("record", help="e.g. conferenceRecords/abc or abc"),
             max_flag(50))),
    ])
