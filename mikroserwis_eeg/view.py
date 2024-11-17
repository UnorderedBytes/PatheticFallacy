import pandas as pd
import matplotlib.pyplot as plt

# Ścieżka do pliku CSV
input_file = "brainaccess_data.csv"

def plot_channels(file_path):
    try:
        # Wczytanie danych z pliku CSV
        df = pd.read_csv(file_path)

        # Sprawdzenie, czy są dane w pliku
        if df.empty:
            print("The file is empty. Please ensure the file contains data.")
            return

        # Iteracja przez kolumny kanałów
        channels = [col for col in df.columns if col.startswith("ch")]
        if not channels:
            print("No channel data found in the file.")
            return

        for channel in channels:
            plt.figure()
            plt.plot(df[channel], label=channel)
            plt.title(f"Samples for {channel}")
            plt.xlabel("Sample Number")
            plt.ylabel("Amplitude")
            plt.legend()
            plt.grid()
            plt.show()

    except FileNotFoundError:
        print(f"File {file_path} not found. Please ensure the file path is correct.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    plot_channels(input_file)
