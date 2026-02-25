import csv
import re
import os

def convert_index_md_to_csv(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove trailing periods if any (like on the last line)
            if line.endswith('.'):
                line = line[:-1]

            # Split by whitespace (one or more spaces/tabs)
            # Re.split handles varying amounts of whitespace
            parts = re.split(r'\s+', line)
            
            if parts:
                writer.writerow(parts)

    print(f"Successfully converted {input_file} to {output_file}")

if __name__ == "__main__":
    convert_index_md_to_csv("index.md", "index.csv")
