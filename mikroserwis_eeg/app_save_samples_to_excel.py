import warnings
import pathlib
import logging
import time
import csv
import os
import pandas as pd

import brainaccess_board as bb

warnings.filterwarnings("ignore")

# Logger configuration
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class CSVLoggerApp:
    def __init__(self, output_file="output.csv") -> None:
        self.db = None
        self.db_status = False
        self.output_file = output_file
        self.prevrange = {}
        self.channels_to_include = [1, 2, 3, 4]  # Channels to include

    def setup(self):
        """
        Sets up database connection and initializes the CSV file.
        """
        root_dir = pathlib.Path(__file__).parent
        logger.info(f"Code placed here: {root_dir}")

        self.db, self.db_status = bb.db_connect()
        if not self.db_status:
            logger.error("Database connection failed")
            raise ConnectionError("Failed to connect to the database.")
        
        logger.info("Database connection successful")
        self._initialize_csv_file()

    def _initialize_csv_file(self):
        """
        Initializes the CSV file with headers if it doesn't exist.
        """
        if not os.path.exists(self.output_file):
            headers = [f"ch{i}" for i in self.channels_to_include]
            with open(self.output_file, mode="w", newline="") as file:
                csv.writer(file).writerow(headers)
            logger.info(f"Initialized CSV file with headers: {headers}")

    def _fetch_and_write_data(self):
        """
        Fetches data from the database and writes it to the CSV file.
        """
        if not self.db_status:
            logger.error("No database connection available.")
            return

        data = self.db.get_mne()
        if not data:
            logger.warning("No data available, please connect the device in the board configuration.")
            return

        for device, device_data in data.items():
            self._process_device_data(device, pd.DataFrame(device_data.get_data().T))

    def _process_device_data(self, device, data_chunk):
        """
        Processes and writes data for a specific device to the CSV file.
        Filters only the channels defined in `channels_to_include`.
        """
        # Filter only selected channels
        filtered_chunk = data_chunk.iloc[:, [ch - 1 for ch in self.channels_to_include]]

        previous_range = self.prevrange.get(device, 0)
        new_chunk = filtered_chunk.iloc[previous_range:]

        if new_chunk.empty:
            logger.info(f"No new data for device {device}")
            return

        self.prevrange[device] = len(filtered_chunk)
        logger.info(f"Device: {device} - Writing filtered data to CSV...")
        new_chunk.to_csv(self.output_file, mode="a", index=False, header=False)

    def run(self):
        """
        Periodically fetches data and writes it to a CSV file.
        """
        logger.info("Starting data fetch loop...")
        try:
            while True:
                self._fetch_and_write_data()
                time.sleep(0.5)  # Adjust the period as needed
        except KeyboardInterrupt:
            logger.info("Exiting on user request.")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    app = CSVLoggerApp(output_file="brainaccess_data.csv")
    try:
        app.setup()
        app.run()
    except Exception as e:
        logger.error(f"Application failed: {e}")
