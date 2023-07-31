import argparse
import platform
import re
import subprocess
import time
from datetime import datetime

import psutil

ARRAY_SIZES: list[int] = [
    100_000_000,
    200_000_000,
    300_000_000,
    400_000_000,
    430_080_000,
]


WHITESPACE_REPLACE = re.compile(r"\s+")


# {uname}_stream_{NUMA}_{yyyymmdd}.csv
def dump_file_name(numa_nodes: str) -> str:
    platform_name = platform.system()
    now = datetime.now().strftime(r"%Y%m%d")

    return f"{platform_name}_stream_{numa_nodes}_{now}.csv"


def core_count_per_socket() -> list[int]:
    command = ["lscpu", "-p=SOCKET"]
    output = subprocess.check_output(command).decode("utf-8")
    socket_count = len(set(x for x in output.split("\n")[4:] if len(x)))
    total_core_count = psutil.cpu_count(logical=False)

    cores = int(total_core_count / socket_count)

    return [1, *[x * 2 for x in range(1, (cores // 2) + 1)]]


def format_stream_output(
    s: str, thread_count: int, array_size: int
) -> list[list[int | str]]:
    selected_output = s.splitlines()[-12:-3]

    lst: list[list[str]] = [
        WHITESPACE_REPLACE.split(str(x, "utf-8", "ignore")) for x in selected_output
    ]

    lst[0].insert(0, "ArraySize")
    lst[0].insert(0, "Threads")
    for i in range(1, len(lst)):
        lst[i][0] = lst[i][0].removesuffix(":")
        lst[i].insert(0, array_size)
        lst[i].insert(0, thread_count)

    return lst


def run_cmd(cmd: str) -> str:
    returned_output = subprocess.check_output(cmd, shell=True)

    return returned_output


def main() -> None:
    parser = argparse.ArgumentParser(description="STREAM benchmarking tool runner")

    parser.add_argument(
        "-b",
        "--binary-path",
        type=str,
        required=True,
        help="Where the stream binary/executable is located",
    )

    parser.add_argument(
        "-n",
        "--numa-nodes",
        required=True,
        type=str,
        help="Numa node(s) to be allocated",
    )

    parser.add_argument(
        "-r",
        "--ntimes",
        type=int,
        required=False,
        default=100,
        help="How many times each for loop should run for",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=False,
        help="Where the output file should be located",
    )

    parser.add_argument(
        "-a",
        "--array-sizes",
        type=int,
        required=False,
        nargs="+",
        default=ARRAY_SIZES,
        help="The arrays that should be ran",
    )

    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        required=False,
        nargs="+",
        default=core_count_per_socket(),
        help="The thread counts that the program should use",
    )

    args = parser.parse_args()

    output = (
        args.output if args.output else dump_file_name(args.numa_nodes.replace(",", ""))
    )

    lst = []

    for thread_count in args.threads:
        for array_size in args.array_sizes:
            cmd = (
                f"export OMP_NUM_THREADS={thread_count} && "
                f"numactl --cpunodebind=0 "
                f"./{args.binary_path} --ntimes {args.ntimes} "
                f"--numa-nodes {args.numa_nodes} --array-size {array_size}"
            )

            start = time.time()
            cmd_stdout = run_cmd(cmd)
            formatted = format_stream_output(cmd_stdout, thread_count, array_size)
            lst.extend(formatted)
            end = time.time()
            elapsed = round(end - start, 3)
            print(
                f"Done in {elapsed}s : {thread_count} threads, {array_size} array size"
            )

    header = lst[0]
    filtered = list(filter(lambda x: x != header, lst))
    filtered.insert(0, header)

    out = [(",".join(str(y) for y in x) + "\n") for x in filtered]

    with open(output, mode="w") as f:
        f.writelines(out)


if __name__ == "__main__":
    main()
