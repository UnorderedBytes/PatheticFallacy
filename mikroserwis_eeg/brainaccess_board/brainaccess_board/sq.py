import sqlite3
import pathlib
import numpy as np
import io
import threading

from typing import Union, Optional, List, Dict

lock = threading.Lock()


def adapt_array(arr: np.ndarray) -> sqlite3.Binary:
    """
    Converts a NumPy array to a binary format for storing in SQLite.
    """
    out = io.BytesIO()
    np.save(out, arr)
    out.seek(0)
    return sqlite3.Binary(out.read())


def convert_array(text: bytes) -> np.ndarray:
    """
    Converts a binary format back to a NumPy array.
    """
    out = io.BytesIO(text)
    out.seek(0)
    return np.load(out)


sqlite3.register_adapter(np.ndarray, adapt_array)
sqlite3.register_converter("array", convert_array)


def get_handle(name: Union[pathlib.Path, str], uri: bool = False) -> Dict:
    """
    Establishes a connection to an SQLite database and sets up the cursor.

    Parameters:
    name (Union[pathlib.Path, str]): Path to the SQLite database file.
    uri (bool): Whether to treat the name as a URI.

    Returns:
    Dict: A dictionary containing the cursor and connection objects.
    """
    con = sqlite3.connect(
        str(name),
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        uri=uri,
    )
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=wal")
    return {"cur": cur, "con": con}


def query(handle: Dict, sql_query: str) -> List:
    """
    Executes a given SQL query and fetches all results.

    Parameters:
    handle (Dict): The database handle containing cursor and connection.
    sql_query (str): The SQL query to execute.

    Returns:
    List: Query results.
    """
    with lock:
        try:
            handle["cur"].execute(sql_query)
            return handle["cur"].fetchall()
        except Exception as e:
            print(f"Error at query {sql_query}: {e}")
            return []


def get_tables(handle: Dict) -> List[str]:
    """
    Retrieves the list of all tables in the database.

    Parameters:
    handle (Dict): The database handle.

    Returns:
    List[str]: A list of table names.
    """
    sql_query = """SELECT name FROM sqlite_master WHERE type='table';"""
    return query(handle, sql_query)


def get_table(handle: Dict, name: str, name2: Optional[str] = None) -> Optional[str]:
    """
    Finds a specific table based on given name patterns.

    Parameters:
    handle (Dict): The database handle.
    name (str): Primary name pattern.
    name2 (Optional[str]): Secondary name pattern.

    Returns:
    Optional[str]: The table name if found, else None.
    """
    tables = get_tables(handle)
    if not tables:
        return None
    for table in tables:
        if name in table[0]:
            if name2 and name2 in table[0]:
                return table[0]
            elif not name2:
                return table[0]
    return None


def get_metadata(handle: Dict, device: str) -> List:
    """
    Fetches metadata for a given device from the database.

    Parameters:
    handle (Dict): The database handle.
    device (str): The device identifier.

    Returns:
    List: Metadata records.
    """
    meta = get_table(handle, name="meta", name2=device)
    if not meta:
        return []
    sql_query = f"select channels, channels_type, channels_unit, sf, id from `{meta}`"
    return query(handle, sql_query)


def get_first_timestamp(handle: Dict, device: str) -> Optional[float]:
    """
    Gets the earliest timestamp from a data table for a specific device.

    Parameters:
    handle (Dict): The database handle.
    device (str): The device identifier.

    Returns:
    Optional[float]: The earliest timestamp if found, else None.
    """
    data = get_table(handle, name="data", name2=device)
    if not data:
        return None
    sql_query = f"SELECT MIN(local_clock) FROM `{data}`"
    result = query(handle, sql_query)
    return result[0][0] if result else None


class InvalidDirectionError(Exception):
    pass


def get_data(
    handle: Dict,
    device: Optional[str] = None,
    direction: str = "last",
    count: int = 10,
) -> list:
    """
    Retrieves data from a table based on the direction and count of records.

    Parameters:
    handle (Dict): The database handle.
    device (Optional[str]): The device identifier.
    direction (str): Direction of retrieval ('all', 'last', 'first').
    count (int): Number of records to retrieve.

    Returns:
    List: Data records.
    """
    data = get_table(handle, name="data", name2=device)
    if not data:
        return []
    if direction == "all":
        sql_query = (
            f"select data, time, local_clock from `{data}` ORDER BY local_clock DESC"
        )
    elif direction == "last":
        sql_query = f"SELECT data, time, local_clock FROM `{data}` ORDER BY local_clock DESC LIMIT {count}"
    elif direction == "first":
        sql_query = f"SELECT data, time, local_clock FROM `{data}` ORDER BY local_clock INC LIMIT {count}"
    else:
        raise InvalidDirectionError("Direction must be 'all', 'last', or 'first'.")
    return query(handle, sql_query)


def get_last_seconds_data(handle: Dict, device: str, duration: int) -> List:
    """
    Retrieves data from the last given number of seconds.

    Parameters:
    handle (Dict): The database handle.
    device (str): The device identifier.
    duration (int): The duration in seconds.

    Returns:
    List: Data records.
    """
    data = get_table(handle, name="data", name2=device)
    if not data:
        return []
    sql_query = f"SELECT data, time, local_clock FROM `{data}` WHERE local_clock+{duration} > (SELECT MAX(local_clock) FROM `{data}`) ORDER BY local_clock DESC"
    return query(handle, sql_query)


def get_devices(handle: Dict) -> List[str]:
    """
    Lists all devices based on the tables available in the database.

    Parameters:
    handle (Dict): The database handle.

    Returns:
    List[str]: A list of device identifiers.
    """
    tables = get_tables(handle)
    devices: list = []
    if not tables:
        return devices
    for table in tables:
        if "meta" in table[0]:
            devices.append(table[0].split("_")[1])
    return devices


def get_data_after(handle: Dict, start: float, column: str, device: str) -> List:
    """
    Retrieves data records that have a timestamp greater than the specified start time.

    Parameters:
    handle (Dict): The database handle.
    start (float): The start time.
    column (str): The column to compare the time.
    device (str): The device identifier.

    Returns:
    List: Data records.
    """
    data = get_table(handle, name="data", name2=device)
    sql_query = f"SELECT data, time, local_clock FROM `{data}` WHERE {column} > {start} ORDER BY {column}"
    return query(handle, sql_query)


def close_db(handle: Dict) -> None:
    handle["con"].close()
