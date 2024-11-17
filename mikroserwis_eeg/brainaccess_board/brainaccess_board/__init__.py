from .database import ReadDB
from .message_queue import BoardControl
from .stream import Stimulation


def stimulation_connect(name: str = "BrainAccessMarkers") -> Stimulation:
    return Stimulation(name=name)


def msg_connect() -> tuple:
    board_control = BoardControl(request_timeout=100)
    response = board_control.get_commands()
    if "data" not in response:
        return None, None, True
    commands = response["data"]
    command = commands["test"]
    reply = board_control.command(command)
    if reply["message"] == "Connection successful":
        return board_control, commands, False
    return board_control, commands, True


def db_connect(filename: str = "current") -> tuple:
    db_status = False
    db = None
    try:
        db = ReadDB(filename)
        if db.handle:
            db_status = True
    except Exception:
        db = None
        db_status = False
    return db, db_status
