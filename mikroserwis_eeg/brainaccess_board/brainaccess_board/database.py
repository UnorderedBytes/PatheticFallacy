from typing import Any, Optional
import re
import numpy as np
import mne
from .utils import get_utils_dict, convert_to_mne
from .sq import (
    get_handle,
    get_data_after,
    get_devices,
    get_data,
    get_last_seconds_data,
    get_metadata,
    get_first_timestamp,
    close_db,
)


class ReadDB:
    """Get current database file to read from it"""

    def __init__(self, filename: str = "current") -> None:
        self.name = filename
        self._connect()
        self._close()

    def _get_current(self) -> str:
        p = get_utils_dict()
        if p:
            current_filename = p.current_save_file
        else:
            raise Exception("No current file found")
        return current_filename

    def _connect(self) -> None:
        if self.name == "current":
            self.filename = self._get_current()
        else:
            self.filename = self.name
        self.handle = get_handle(self.filename, uri=True)
        self.devices = get_devices(self.handle)

    def _close(self) -> None:
        close_db(handle=self.handle)

    def _get_data(
        self,
        device: str,
        chunk_count: Optional[int] = None,
        duration: Optional[int] = None,
        time_range: Optional[tuple] = None,
    ) -> dict[str, Any]:
        data = None
        if duration:
            data = get_last_seconds_data(self.handle, duration=duration, device=device)
        elif time_range:
            data = get_data(self.handle, device=device, direction="all")
        elif chunk_count:
            data = get_data(self.handle, count=chunk_count, device=device)
        else:
            data = get_data(self.handle, device=device, direction="all")
        if not data:
            return {}
        else:
            _data = np.block([x[0] for x in data[::-1]])
            _time = np.block([x[1] for x in data[::-1]])
            _l = np.block([x[2] for x in data[::-1]])
            return {
                "data": _data,
                "time": _time,
                "local_time": _l,
                "id": device,
            }

    def _get_info(self, device: str) -> dict[str, Any]:
        _info = get_metadata(self.handle, device=device)
        first_timestamp = get_first_timestamp(self.handle, device=device)
        # if not first_timestamp:
        #     return {}
        if not _info:
            info: dict = {}
        else:
            info = {
                "channels": [x for x in _info[0][0].split(",")],
                "channels_type": [x for x in _info[0][1].split(",")],
                "channels_unit": [x for x in _info[0][2].split(",")],
                "srate": _info[0][3],
                "id": _info[0][4],
                "first_timestamp": first_timestamp,
            }
        return info

    def list_devices(self, only_lsl: bool = False) -> dict[str, Any]:
        self.devices = get_devices(self.handle)
        markers = {}
        data_devices = {}
        for device in self.devices:
            info = self._get_info(device)
            if not info:
                continue
            if info["srate"] > 0:
                if only_lsl:
                    if not len(re.findall(r"-", device)) == 4:
                        continue
                data_devices[device] = info
            else:
                markers[device] = info
        return {"data": data_devices, "markers": markers}

    def _convert_to_mne(self, data: dict, markers: dict, meta: dict) -> mne.io.Raw:
        """Convert data to mne format

        Args:
            data (dict): data to convert
            markers (dict): markers to convert
            meta (dict): metadata to convert

        Returns:
            mne.raw converted data

        """
        data["meta"] = meta
        data = convert_to_mne(data, markers)
        return data

    def _get_marker_data(self, time: float, column_name: str, device: str) -> dict:
        data = get_data_after(
            self.handle, start=time, column=column_name, device=device
        )
        if not data:
            return {}
        else:
            _data = np.block([x[0] for x in data[::-1]])
            _time = np.block([x[1] for x in data[::-1]])
            _l = np.block([x[2] for x in data[::-1]])
            return {"data": _data, "time": _time, "local_time": _l, "id": device}

    def get_mne(
        self,
        device: Optional[str] = None,
        duration: Optional[int] = None,
        time_range: Optional[tuple] = None,
        only_lsl: bool = True,
        marker_devices_include: Optional[list[str]] = None,
    ) -> dict[str, mne.io.Raw]:
        self._connect()
        all_devices = self.list_devices(only_lsl=only_lsl)
        if device is None:
            data_devices = list(all_devices["data"].keys())
        else:
            data_devices = [device]
        markers = {}
        if marker_devices_include:
            for dev in marker_devices_include:
                if not dev:
                    continue
                try:
                    markers[dev] = self._get_data(device=dev)
                except Exception:
                    print(f"Device {dev} not found")
        else:
            for dev in all_devices["markers"]:
                _dat = self._get_data(device=dev)
                if _dat:
                    markers[dev] = _dat
        meta = {}
        mne_data = {}
        for dev in data_devices:
            data = self._get_data(device=dev, duration=duration, time_range=time_range)
            meta = self._get_info(device=dev)
            mne_data[dev] = self._convert_to_mne(data, markers, meta)
        self._close()
        return mne_data
