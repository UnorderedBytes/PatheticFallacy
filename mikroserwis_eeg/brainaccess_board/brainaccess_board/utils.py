import json
import socket
import numpy as np
import mne
import pathlib
import appdirs
from contextlib import closing

from collections import defaultdict
from pydantic import ValidationError, BaseModel


user_log_dir: pathlib.Path = pathlib.Path(
    appdirs.user_log_dir(appname="baboard", appauthor="Neurotechnology")
)
user_log_utils = user_log_dir.joinpath("utils.json")


class RunningSessionOptions(BaseModel):
    """Running session options"""

    current_save_file: str
    socket_port: int


def get_utils_dict() -> RunningSessionOptions | None:
    try:
        with open(user_log_utils, "r", encoding="utf-8") as f:
            _f = json.load(f)
            _RUNNING: RunningSessionOptions = RunningSessionOptions.parse_obj(_f)
        return _RUNNING
    except ValidationError as e:
        print(e)
        return None


def convert_to_mne(
    data: dict,
    markers: dict,
) -> mne.io.RawArray:
    """Convert data to MNE RawArray

    Args:
        data (dict): data to convert
        markers (dict): markers to add to the data

    Returns:
        mne.io.RawArray: converted data

    """
    info = create_info(data)
    data_units = get_units_conversion(data)
    data["data"] = data["data"] * data_units
    raw_data = mne.io.RawArray(data["data"], info)
    onset = np.array([])
    description = []
    duration = []
    if markers:
        data_time0 = data["time"][0]
        for marker in markers:
            try:
                onset = np.append(onset, np.array(markers[marker]["time"]) - data_time0)
            except Exception as e:
                print(f"Error in marker {marker} {e}")
                continue
            description.extend([x for x in markers[marker]["data"][0]])
        duration = [0 for _ in onset]
    annot = mne.Annotations(
        onset=onset,
        duration=duration,
        description=description,
    )
    raw_data.set_annotations(annot)
    raw_data.set_montage("standard_1005", on_missing="warn")
    return raw_data


def create_info(data: dict) -> mne.Info:
    """Create MNE Info object from data.

    Args:
        data (dict): Data to extract info from.

    Returns:
        mne.Info: MNE Info object.
    """
    channel_types = [
        "eeg" if _type == "EEG" else "misc" for _type in data["meta"]["channels_type"]
    ]
    info = mne.create_info(
        ch_names=data["meta"]["channels"],
        ch_types=channel_types,
        sfreq=data["meta"]["srate"],
    )
    info.set_montage("standard_1005", on_missing="warn")
    return info


def get_units_conversion(data: dict) -> np.ndarray:
    """Get conversion factors for data units.

    Args:
        data (dict): Data to extract units from.

    Returns:
        np.array: Conversion factors for each channel.
    """
    conversions: defaultdict = defaultdict(lambda: 1)
    conversions.update(
        {
            "microvolts": 1e-6,
            "volts": 1,
            "mV": 1e-3,
            "uV": 1e-6,
            "millivolts": 1e-3,
            "V": 1,
        }
    )
    result = []
    for data_type, unit in zip(
        data["meta"]["channels_type"], data["meta"]["channels_unit"]
    ):
        result.append(conversions[unit])
    return np.array(result).reshape(-1, 1)


def find_free_port() -> int:
    """Find a free port on the localhost

    Returns:
        int: Port number
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as free_socket:
        free_socket.bind(("localhost", 0))
        free_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port_number = free_socket.getsockname()[1]
        return port_number
