import zmq
import time
import logging
from typing import Any

from .utils import get_utils_dict


level_map = {
    "debug": 10,
    "info": 20,
    "warning": 30,
    "error": 40,
    "critical": 50,
}


commands: dict[str, dict[str, Any]] = {}
commands["commands"] = {
    "command": "commands",
    "description": "get all possible commands",
    "message": "",  # message to log to file
    "level": "info",  # log level
    "source": "client",
}
commands["error"] = {
    "command": "error",
    "message": "Invalid message",
    "source": "client",
}


class SocketClient:
    def __init__(
        self,
        port: int,
        commands: dict,
        mode: str = "json",
        request_timeout: int = 22500,
        logger: logging.Logger | None = None,
    ) -> None:
        self.mode = mode
        self.REQUEST_TIMEOUT = request_timeout
        self.commands = commands
        self.REQUEST_RETRIES = 3
        self.SERVER_ENDPOINT = f"tcp://localhost:{port}"
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(self.SERVER_ENDPOINT)
        self.logger = logger

    def log(self, message: str, level: str = "info") -> None:
        if self.logger:
            self.logger.log(level_map[level], message)
        else:
            print(f"{level.upper()}: {message}")

    def command(self, command: dict) -> dict:
        """Send command to board

        Args:
            command (dict): message to send
        Returns:
            reply (dict): reply from board
        """
        if not isinstance(command, dict):
            return self._invalid_command_response("Invalid command type, must be dictionary, check possible commands")
        return self._attempt_command(command)

    def _attempt_command(self, command: dict) -> dict:
        self._send(command)
        retries_left = self.REQUEST_RETRIES
        while retries_left > 0:
            try:
                if (self.socket.poll(self.REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                    return self._receive()
            except zmq.ZMQError as e:
                self.log(f"ZMQ Error: {e}", level="error")

            retries_left -= 1
            self.log("No response from server, retrying...", level="warning")
            time.sleep(1)
            self._reset_socket()

        return {
            "command": command["command"],
            "direction": "reply",
            "message": "Server seems to be offline. Connection error",
        }

    def _reset_socket(self) -> None:
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(self.SERVER_ENDPOINT)

    def _invalid_command_response(self, message: str) -> dict:
        self.log(message, level="error")
        reply = self.commands["error"].copy()
        reply["message"] = message
        reply["source"] = "client"
        return reply

    def _send(self, obj: dict) -> None:
        """Send a json object"""
        if self.mode == "json":
            self.socket.send_json(obj)
        else:
            self.socket.send_pyobj(obj)

    def _receive(self) -> dict:
        """Receive a json or pickle object"""
        if self.mode == "json":
            message = self.socket.recv_json()
        else:
            message = self.socket.recv_pyobj()
        if not isinstance(message, dict):
            self.log("Received invalid message", level="error")
            reply = self.commands["error"].copy()
            reply["message"] = "Received invalid message"
            return reply
        return message

    def get_commands(self) -> dict:
        return self.command(self.commands["commands"])


class BoardControl(SocketClient):
    """Board  model and GUI control via messages"""

    def __init__(
        self, logger: logging.Logger | None = None, request_timeout: int = 22500
    ) -> None:
        try:
            utils = get_utils_dict()
            if utils is None:
                raise Exception("Board is not connected")
            port = utils.socket_port
        except Exception as e:
            self.log(f"Socket port not found: {str(e)}", level="error")
            raise Exception("Socket port not found, please restart the app")
        super().__init__(
            port, commands, logger=logger, mode="json", request_timeout=request_timeout
        )
        self.log(f"Board Control created using port: {port}")
