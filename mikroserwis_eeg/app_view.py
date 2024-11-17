import warnings
import panel as pn
import pathlib
import logging

import brainaccess_board as bb
from brainaccess_board.utils import find_free_port

root_dir = pathlib.Path(__file__).parent
logo = root_dir / "image.png"

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class VIEW:
    def __init__(self) -> None:
        self.app = None

    def setup(self):
        """Sets up all widgets"""
        text = f"""
This is an example of an app for the BrainAccess Board platform.
The app demonstrates interaction with the BrainAccess Board database.
It gets data from the Board database and prints it to the screen.

Code placed here: {root_dir}
"""
        self.text_field = pn.widgets.StaticText(name="", value=text)

        self.data_field = pn.widgets.StaticText(
            name="data", value="Data will be here")
        self.db, self.db_status = bb.db_connect()
        if self.db_status:
            self.data_field.value = "Database connection successful"
        else:
            self.data_field.value = "Database connection failed"

    def _periodic_function(self):
        data = self.db.get_mne()
        if not data:
            self.data_field.value = "No data available, please connect the device in the board configuration"
        devices = list(data.keys())
        for device in devices:
            field = f"Device: {device}\n\n Data: {data[device].get_data()}"
            self.data_field.value = field

    def start(self):
        """Manages layout and exposes main and sidebar fields"""
        row1 = pn.Row(self.text_field)
        row2 = pn.Row(self.data_field)
        main = pn.Column(
            pn.Spacer(),
            pn.Row(
                pn.layout.HSpacer(),
                pn.Column(
                    row1,
                    row2,
                ),
                pn.layout.HSpacer(),
            ),
            pn.Spacer(),
        )
        sidebar = []
        return main, sidebar

    def get_app(self):
        self.setup()
        main, sidebar = self.start()
        logo_element = pn.Row(
            pn.pane.PNG(logo, height=50, width=50),
        )
        self.periodic_function = pn.state.add_periodic_callback(self._periodic_function, start=True, period=500)
        self.app = pn.template.ReactTemplate(
            title="Example APP",
            site="",
            header=[pn.Row(logo_element, pn.layout.HSpacer())],
            favicon=logo,
            main=main,
            sidebar=sidebar,
            modal=[],
        )
        if self.app.busy_indicator:
            self.app.busy_indicator.visible = False
        logger.warning("Setup done")
        return self.app


def destroy(_):
    """Executed after browser window is closed"""
    app.stop()


def create(_):
    pass


def get_app():
    pn.state.on_session_destroyed(destroy)
    view = VIEW()
    app = view.get_app()
    return app


pn.state.on_session_created(create)


pn.extension(
    sizing_mode="stretch_width",
    loading_spinner="petal",
    loading_color="#0b4d3a",
)

app = pn.serve(
    {"App": get_app},
    threaded=True,
    port=find_free_port(),
    show=True,
    autoreload=False,
    title="",
)
