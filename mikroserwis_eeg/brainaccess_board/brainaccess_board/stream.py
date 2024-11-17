import time

from pylsl import StreamInfo, StreamOutlet


class Stimulation:
    """Initialize LSL marker device and use it to send annotations"""

    def __init__(
        self, name: str = "BrainAccessMarkers", source_id: str = "BrainAccessMarkers"
    ) -> None:
        self.info = StreamInfo(
            name=name,
            type="Markers",
            channel_count=1,
            nominal_srate=0,
            channel_format=3,  # "string",
            source_id=source_id,
        )
        self.outlet = StreamOutlet(self.info)
        time.sleep(1)

    def annotate(self, msg: str) -> None:
        self.outlet.push_sample([msg])

    def have_consumers(self) -> bool:
        return self.outlet.have_consumers()
