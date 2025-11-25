import json
import os
import datetime
import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "logfiles"
OUTPUT_DIR.mkdir(exist_ok=True)

def dump_json(response, output_filename):
    filedate = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{output_filename}_{filedate}.json"
    json_file_path = OUTPUT_DIR / filename
    with open(json_file_path, "w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=4)
    print(f"{json_file_path} written")


def dump_dataframe(df, output_filename):
    filedate = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{output_filename}_{filedate}.csv"
    filepath = OUTPUT_DIR / filename
    df.to_csv(filepath, index=False)
    print(f"{filepath} written")
