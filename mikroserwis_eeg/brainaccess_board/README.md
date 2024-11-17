# brainaccess-board

Communication with [BrainAccess Board](https://www.brainaccess.ai/software/brainaccess-board/) and its database.

## Installation

```bash
pip install brainaccess-board
```

## Usage

### Connect to active database

```python
import brainaccess_board as bb

db, status = bb.db_connect()
if status:
    data = db.get_mne()
    print(f"Dictionary of connected devices:\n {data}")
    print(f"MNE structure: {data[next(iter(data))]}")
```

```bash
Dictionary of connected devices:
 {'b2b586a2-da7a-4420-8a6d-cb890e9ba7d7': <RawArray | 8 x 36500 (146.0 s), ~2.
2 MB, data loaded>}

MNE structure: <RawArray | 8 x 36500 (146.0 s), ~2.2 MB, data loaded>
```


### Communication with BrainAccess Board

```python
import brainaccess_board as bb

bc, commands, status = bb.msg_connect()
print(commands)

if status:
    response = bc.command(commands['test'])
    print(response)
```

### Setup LSL Markers

Creates LSL stream with markers.

```python
import brainaccess_board as bb

stim = bb.stimulation_connect(name="BrainAccessMarkers")

if stim.have_consumers():
    stim.annotate("1")
```
