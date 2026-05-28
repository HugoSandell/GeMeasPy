import re
import csv
import sys


def extract(pattern, block, seed):
    m = re.search(pattern, block)
    if m is None:
        raise ValueError(f"Pattern {pattern!r} not found in block for seed {seed}")
    return m.group(1)


def parse_results(text):
    rows = []
    parts = re.split(r'=== Seed (\d+) ===', text)
    for i in range(1, len(parts) - 1, 2):
        seed  = parts[i]
        block = parts[i + 1]
        killed   = extract(r'Killed:\s+(\d+)',     block, seed)
        survived = extract(r'Survived:\s+(\d+)',   block, seed)
        equiv    = extract(r'Equivalent:\s+(\d+)', block, seed)
        uncov    = extract(r'Uncovered:\s+(\d+)',  block, seed)
        incomp    = extract(r'Incompetent:\s+(\d+)',  block, seed)
        rows.append([seed, killed, survived, equiv, uncov, incomp])
    return rows


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <input_file> [output_file]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        text = f.read()

    rows = parse_results(text)

    out = open(sys.argv[2], 'w', newline='') if len(sys.argv) > 2 else sys.stdout
    try:
        writer = csv.writer(out)
        writer.writerow(['Seed', 'Killed', 'Survived', 'Equivalent', 'Uncovered', 'Incompetent'])
        writer.writerows(rows)
    finally:
        if out is not sys.stdout:
            out.close()


if __name__ == '__main__':
    main()
