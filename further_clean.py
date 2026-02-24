import os
import glob
import pandas as pd
import numpy as np
from collections import defaultdict


def load_adj_close_series(folder):
    """Load adj_close series from all CSVs, aligned by date."""
    series = {}
    meta = {}  # store metadata for each file

    csv_files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    print(f"Loading {len(csv_files)} files from '{folder}'...")

    for filepath in csv_files:
        name = os.path.basename(filepath)
        try:
            df = pd.read_csv(filepath)
            if df.empty or 'adj_close' not in df.columns or 'date' not in df.columns:
                continue

            df['date'] = pd.to_datetime(df['date'])
            s = df.set_index('date')['adj_close'].dropna()

            if len(s) < 100:  # skip very short series
                continue

            # Calculate return and last day volume
            total_return = s.iloc[-1] / s.iloc[0] - 1 if s.iloc[0] != 0 else 0
            last_volume = df['volume'].iloc[-1] if 'volume' in df.columns else 0

            series[name] = s
            meta[name] = {
                'filepath': filepath,
                'total_return': total_return,
                'last_volume': last_volume,
                'num_rows': len(s),
            }
        except Exception as e:
            print(f"  Error loading {name}: {e}")

    print(f"Loaded {len(series)} valid series.")
    return series, meta


def find_correlated_groups(series, threshold=0.995):
    """Find groups of ETFs with pairwise correlation > threshold."""
    names = list(series.keys())
    n = len(names)

    # Build a combined DataFrame aligned by date
    print(f"Building correlation matrix for {n} series...")
    combined = pd.DataFrame(series)

    # Use pairwise complete observations for correlation
    corr_matrix = combined.corr(min_periods=100)

    # Find pairs above threshold
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            c = corr_matrix.iloc[i, j]
            if not np.isnan(c) and c > threshold:
                pairs.append((names[i], names[j], c))

    print(f"Found {len(pairs)} highly correlated pairs (>{threshold}).")

    # Union-Find to group transitively correlated ETFs
    parent = {name: name for name in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b, _ in pairs:
        union(a, b)

    # Collect groups
    groups = defaultdict(list)
    for name in names:
        root = find(name)
        groups[root].append(name)

    # Only return groups with more than 1 member
    multi_groups = {k: v for k, v in groups.items() if len(v) > 1}
    singletons = [v[0] for k, v in groups.items() if len(v) == 1]

    print(f"Found {len(multi_groups)} correlated groups, {len(singletons)} unique ETFs.")
    return multi_groups, singletons, pairs


def pick_best(group, meta):
    """Pick the best ETF from a correlated group.
    Priority: longer history (num_rows), then higher last day volume.
    """
    ranked = sorted(
        group,
        key=lambda name: (meta[name]['num_rows'], meta[name]['last_volume']),
        reverse=True,
    )
    return ranked[0], ranked[1:]  # best, rest


def main():
    selected_dir = 'selected'
    output_dir = 'selected2'

    if not os.path.isdir(selected_dir):
        print(f"Error: '{selected_dir}' folder not found.")
        return

    os.makedirs(output_dir, exist_ok=True)

    # 1. Load all series
    series, meta = load_adj_close_series(selected_dir)

    # 2. Find correlated groups
    multi_groups, singletons, pairs = find_correlated_groups(series, threshold=0.995)

    # 3. Print correlated groups for review
    print("\n=== Correlated Groups ===")
    best_names = []
    for i, (root, group) in enumerate(multi_groups.items(), 1):
        best, rest = pick_best(group, meta)
        best_names.append(best)
        print(f"\nGroup {i} ({len(group)} ETFs):")
        for name in group:
            m = meta[name]
            marker = " ★ BEST" if name == best else ""
            print(f"  {name:50s} days={m['num_rows']}  vol={m['last_volume']:>12,.0f}{marker}")

    # 4. Move best from each group + all singletons to selected2
    to_move = best_names + singletons
    print(f"\n=== Moving {len(to_move)} ETFs to '{output_dir}' ===")

    import shutil
    moved = 0
    for name in sorted(to_move):
        src = meta[name]['filepath']
        dst = os.path.join(output_dir, name)
        shutil.copy2(src, dst)  # copy instead of move to keep selected intact
        moved += 1

    print(f"\nDone! Copied {moved} ETFs to '{output_dir}'.")
    print(f"  From {len(multi_groups)} correlated groups: {len(best_names)} best picks")
    print(f"  Unique (no duplicates): {len(singletons)}")


if __name__ == '__main__':
    main()
