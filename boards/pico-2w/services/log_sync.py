"""Log synchronization and pagination utilities for SD card data logs."""

import os


def get_log_files(dir_path):
    """Returns a sorted list of .csv log filenames in dir_path."""
    try:
        files = [f for f in os.listdir(dir_path) if f.endswith(".csv")]
        files.sort()
        return files
    except Exception:
        return []


def parse_cursor(cursor_str, available_files):
    """Parses a cursor string into (target_filename, line_number).

    cursor_str can be:
    - None or empty: defaults to (oldest_file, 0)
    - "YYYY-MM-DD:line" or "YYYY-MM-DD.csv:line"
    Returns (target_filename, line_number) or (None, 0) if no files exist.
    """
    if not available_files:
        return (None, 0)

    if not cursor_str:
        return (available_files[0], 0)

    cursor_str = cursor_str.strip()
    if ":" in cursor_str:
        file_part, line_part = cursor_str.split(":", 1)
        try:
            line_num = int(line_part)
        except ValueError:
            line_num = 0
    else:
        file_part = cursor_str
        line_num = 0

    if not file_part.endswith(".csv"):
        target_file = file_part + ".csv"
    else:
        target_file = file_part

    return (target_file, line_num)


def get_next_file(current_file, available_files):
    """Finds the next sequential file in available_files alphabetically."""
    if not available_files:
        return None
    if current_file in available_files:
        idx = available_files.index(current_file)
        if idx + 1 < len(available_files):
            return available_files[idx + 1]
        return None
    for f in available_files:
        if f > current_file:
            return f
    return None


def read_log_records(dir_path, cursor_str, size):
    """Reads up to `size` data lines from SD card CSV logs starting from `cursor_str`.

    Returns a dict:
    {
        "data": [...],
        "next_cursor": "YYYY-MM-DD:line"
    }
    """
    files = get_log_files(dir_path)
    if not files:
        return {"data": [], "next_cursor": cursor_str if cursor_str else ""}

    target_file, line_num = parse_cursor(cursor_str, files)
    if not target_file:
        return {"data": [], "next_cursor": cursor_str if cursor_str else ""}

    newest_file = files[-1]
    if target_file not in files and target_file > newest_file:
        base_name = newest_file[:-4] if newest_file.endswith(".csv") else newest_file
        return {"data": [], "next_cursor": f"{base_name}:{line_num}"}

    if target_file not in files and target_file < files[0]:
        target_file = files[0]
        line_num = 0

    data = []
    current_file = target_file
    current_line = line_num

    while len(data) < size and current_file:
        file_path = f"{dir_path}/{current_file}"
        try:
            with open(file_path, "r") as f:
                data_line_idx = 0
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    # Skip CSV header
                    if stripped.startswith("timestamp,") or stripped.startswith("timestamp"):
                        continue

                    # Skip rows prior to current_line
                    if data_line_idx < current_line:
                        data_line_idx += 1
                        continue

                    parts = stripped.split(",")
                    if len(parts) >= 4:
                        ts = parts[0].strip()
                        dev_id = parts[1].strip()
                        try:
                            temp = float(parts[2].strip()) if parts[2].strip() != "" else None
                        except ValueError:
                            temp = None
                        try:
                            hum = float(parts[3].strip()) if parts[3].strip() != "" else None
                        except ValueError:
                            hum = None

                        record = {
                            "ts": ts,
                            "device_id": dev_id,
                            "temp": temp,
                            "hum": hum,
                        }
                        if len(parts) >= 5:
                            try:
                                light = float(parts[4].strip()) if parts[4].strip() != "" else None
                            except ValueError:
                                light = None
                            record["light"] = light

                        data.append(record)
                    data_line_idx += 1
                    current_line = data_line_idx

                    if len(data) >= size:
                        break
        except OSError as e:
            print(f"[log_sync] Error reading {file_path}: {e}")
            break

        if len(data) < size:
            next_f = get_next_file(current_file, files)
            if next_f:
                current_file = next_f
                current_line = 0
            else:
                break

    base_name = current_file[:-4] if current_file.endswith(".csv") else current_file
    next_cursor = f"{base_name}:{current_line}"

    return {
        "data": data,
        "next_cursor": next_cursor,
    }
