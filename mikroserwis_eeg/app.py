import warnings
import time
import pathlib
import logging
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
import numpy as np
import brainaccess_board as bb  # Zakładamy, że to niestandardowy moduł
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# Konfiguracja loggera
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

plt.ion()
plt.show(block=False)

app = FastAPI()

stress_finetuning = 1

class SlidingDataFrame:
    def __init__(self, max_length):
        """
        Inicjalizacja obiektu SlidingDataFrame.
        :param max_length: Maksymalna długość bufora.
        """
        self.max_length = max_length
        self.data = pd.DataFrame()

    def add_data(self, new_data):
        """
        Dodaje nowe dane do DataFrame przesuwnego.
        :param new_data: Nowe dane do dodania (jako pd.Series, lista, numpy array lub DataFrame).
        """
        # Zamiana danych na DataFrame z jedną kolumną
        if isinstance(new_data, pd.Series):
            new_data = new_data.to_frame(name="Value")  # Przekształć Series na DataFrame
        elif isinstance(new_data, (list, np.ndarray)):
            new_data = pd.DataFrame(new_data, columns=["Value"])
        elif isinstance(new_data, pd.DataFrame):
            if len(new_data.columns) != 1:
                raise ValueError("The input DataFrame must have exactly one column.")
            new_data.columns = ["Value"]
        else:
            raise ValueError("Input data must be a pandas Series, list, numpy array, or a DataFrame with one column.")

        # Dodanie nowych danych do bufora
        self.data = pd.concat([new_data, self.data], ignore_index=True)

        print(self.data)

        # Skrócenie DataFrame do maksymalnej długości
        if len(self.data) > self.max_length:
            self.data = self.data.iloc[:self.max_length]

    def calculate_mean(self):
        """
        Oblicza średnią arytmetyczną wszystkich danych w DataFrame.
        :return: Średnia arytmetyczna.
        """
        if self.data.empty:
            return None
        print("What do you mean", self.data["Value"].mean())
        return self.data["Value"].mean()

    def calculate_percentage_above_mean(self, other_data):
        """
        Oblicza procent danych w innym zbiorze, które przekraczają średnią.
        :param other_data: Lista, numpy array, Series lub DataFrame z danymi do analizy.
        :return: Procent danych przekraczających średnią.
        """
        mean_value = self.calculate_mean() * stress_finetuning
        if mean_value is None:
            return None

        # Zamiana danych na DataFrame o jednej kolumnie
        if isinstance(other_data, pd.Series):
            other_data = other_data.to_frame(name="Value")
        elif isinstance(other_data, (list, np.ndarray)):
            other_data = pd.DataFrame(other_data, columns=["Value"])
        elif isinstance(other_data, pd.DataFrame):
            if len(other_data.columns) != 1:
                raise ValueError("The input DataFrame must have exactly one column.")
            other_data.columns = ["Value"]
        else:
            raise ValueError("Input data must be a pandas Series, list, numpy array, or a DataFrame with one column.")

        total_values = len(other_data)
        if total_values == 0:
            return None
        count_above_mean = (other_data["Value"] > mean_value).sum()
        return (count_above_mean / total_values) * 100

class EEGProcessor:
    def __init__(self) -> None:
        self.db = None
        self.db_status = False
        self.prevrange = 0
        self.channels_to_include = [1, 2, 3, 4]  # Wybrane kanały
        self.latest_relaxation = None
        self.latest_stress = None

        # Stress detection
        self.stress_threshold = 100
        self.historical_data = pd.DataFrame(columns=["fp2", "fp1", "o2", "o1"])

        self.sliding_df = SlidingDataFrame(max_length=3000)        

        # Lock dla bezpieczeństwa wątków
        self.lock = asyncio.Lock()

    async def setup(self):
        """
        Inicjalizacja połączenia z bazą danych.
        """
        root_dir = pathlib.Path(__file__).parent
        logger.info(f"Kod znajduje się w: {root_dir}")

        self.db, self.db_status = bb.db_connect()
        if not self.db_status:
            logger.error("Nie udało się połączyć z bazą danych")
            raise ConnectionError("Nie udało się połączyć z bazą danych.")

        logger.info("Połączenie z bazą danych udane")

    async def _fetch_data(self):
        """
        Pobiera dane z bazy danych.
        """
        if not self.db_status:
            logger.error("Brak dostępnego połączenia z bazą danych.")
            return None

        ### TO NIE DZIAŁA
        sampling_rate = 100  # Przykładowa liczba próbek na sekundę
        num_samples = 800
        # Zakładamy czas trwania danych w sekundach
        duration = num_samples / sampling_rate
        # Zakładamy początek zakresu od czasu 0
        start_time = 0
        end_time = start_time + duration
        # Tworzymy krotkę dla `time_range`
        time_range = (start_time, end_time)
        # Wywołanie funkcji
        #data = self.db.get_mne(time_range=time_range)
        ###

        data = self.db.get_mne()
        if not data:
            logger.warning("Brak dostępnych danych, proszę podłączyć urządzenie w konfiguracji płytki.")
            return None

        for device, device_data in data.items():
            data_chunk = pd.DataFrame(device_data.get_data().T)
            unfiltered = data_chunk.iloc[:, [ch - 1 for ch in self.channels_to_include]]
            filtered = unfiltered[self.prevrange:]
            self.prevrange = len(unfiltered)
            return filtered

        return None

    async def _compute_levels(self, data_chunk):
        """
        Oblicza poziomy relaksu i stresu na podstawie danych.
        """
        if data_chunk is None or data_chunk.empty:
            return

        # ELEKTRODA o1
        o1 = data_chunk[0]
        self.sliding_df.add_data(o1)
        stress_threshold = self.sliding_df.calculate_mean()
        percentage_above_mean = self.sliding_df.calculate_percentage_above_mean(o1)

        # IMPEDANCE_DRIVE_AMPS = 6.0e-9  # 6 nA
        # BOARD_RESISTOR_OHMS = 2 * 4.7e3  # 4.7 kOhm

        # # o1 = data_chunk[0]
        # # print("o1 first element: ", o1[self.prevrange-1])
        # # print("GG: ", (
        # #     (np.sqrt(2.0) * o1[self.prevrange-1] * 1.0e-6) / IMPEDANCE_DRIVE_AMPS - BOARD_RESISTOR_OHMS
        # # ))
        # # print("o1 uV: ", o1[self.prevrange-1] * BOARD_RESISTOR_OHMS) # uV

        # data = np.std(data_chunk, axis=1)
        # impedance = (
        #     (np.sqrt(2.0) * data * 1.0e-6) / IMPEDANCE_DRIVE_AMPS - BOARD_RESISTOR_OHMS
        # ) / 1000
        # impedance[impedance < 0] = 0

        # print(impedance)
        
        # print("GG: ", (
        #     (np.sqrt(2.0) * o1[self.prevrange-1] * 1.0e-6) / IMPEDANCE_DRIVE_AMPS - BOARD_RESISTOR_OHMS
        # ))

        #relaxation_level = max(0, min(100, 50 + data_chunk.mean().mean() + fluctuation))
        #stress_level = 100 - relaxation_level

        #print("relaxation_level: ", relaxation_level)
        #print("stress_level: ", stress_level)
        # plt.close()
        # time.sleep(0.001)
        # plt.plot(impedance.head(100))
        # plt.draw()
        # plt.pause(0.0001)

        print(len(o1))
        print("----------------------------")

        # W TE ZMIENNE ZAPISUJEMY DANE, KTÓRE LĄDUJĄ NA API
        relaxation_level = 100 - percentage_above_mean
        # stress_level = 100 - relaxation_level
        stress_level = 0  #o1[self.prevrange-1]

        print("Relaxation level: ", relaxation_level)

        async with self.lock:
            self.latest_relaxation = relaxation_level
            
            if (relaxation_level > 75):
                self.latest_stress = 0
            elif (relaxation_level > 50):
                self.latest_stress = 1
            elif (relaxation_level > 25):
                self.latest_stress = 2
            else:
                self.latest_stress = 3


    async def data_fetching_task(self):
        """
        Zadanie w tle do ciągłego pobierania danych i obliczania poziomów.
        """
        while True:
            data_chunk = await self._fetch_data()

            await self._compute_levels(data_chunk)
            await asyncio.sleep(.5)  # Możesz dostosować interwał czasowy

    async def get_latest_levels(self):
        """
        Zwraca najnowsze obliczone poziomy.
        """
        async with self.lock:
            return self.latest_relaxation, self.latest_stress

processor = EEGProcessor()

@app.on_event("startup")
async def startup_event():
    await processor.setup()
    # Uruchomienie zadania w tle
    asyncio.create_task(processor.data_fetching_task())

@app.get("/get_levels")
async def get_levels():
    relaxation, stress = await processor.get_latest_levels()
    if relaxation is None or stress is None:
        return JSONResponse(status_code=503, content={"message": "Brak dostępnych danych"})
    return stress 

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
