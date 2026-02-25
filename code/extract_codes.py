import re
import os
import csv

def extract_codes(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} does not exist.")
        return

    # 1. Load existing entries from list.csv if it exists
    unique_entries = {}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None) # Skip header
            for row in reader:
                if len(row) >= 2:
                    code, name = row[0], row[1]
                    unique_entries[code] = name

    # 2. Extract new entries from list.md
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i in range(len(lines)):
        # Match 6-digit code inside square brackets
        match = re.search(r'\[(\d{6})\]', lines[i])
        if match:
            code = match.group(1)
            # The name is 2 lines below (index i + 2)
            if i + 2 < len(lines):
                name = lines[i+2].strip()
                if name:
                    # Update or add (if same code exists, it will be updated with new version)
                    unique_entries[code] = name

    # 3. Sort entries by code
    sorted_codes = sorted(unique_entries.keys())

    # 4. Save combined results back to list.csv
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["code", "name"])
        for code in sorted_codes:
            writer.writerow([code, unique_entries[code]])

    print(f"Combined total: {len(unique_entries)} unique codes and names in {output_file}")

if __name__ == "__main__":
    input_path = "/home/hallo/Documents/alpha/etf/list.md"
    output_path = "/home/hallo/Documents/alpha/etf/list.csv"
    extract_codes(input_path, output_path)
