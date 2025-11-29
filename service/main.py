import json
import os
import platform
import subprocess
from datetime import datetime
import hashlib
from functools import lru_cache
from multiprocessing import Pool

from config import OUTPUT_DIRECTORY, GROUPS, MAX_THREADS

# Команды для расчета контрольных сумм
checksum_cmds = {
    "linux": {"sha256": "sha256sum", "md5": "md5sum", "split_number": 0},
    "freebsd": {"sha256": "sha256sum", "md5": "md5sum", "split_number": 0},
    "sunos": {"sha256": "sha256sum", "md5": "md5sum", "split_number": 0},
    "darwin": {"sha256": "sha256sum", "md5": "md5sum", "split_number": 0},
    "openbsd": {"sha256": "sha256", "md5": "md5", "split_number": -1},
}


def exec_command(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.stdout


def get_threads_count():
    if MAX_THREADS is not None:
        return MAX_THREADS
    try:
        output = subprocess.check_output(
            ['lscpu'],
            text=True,
            env={**os.environ, 'LC_ALL': 'C'}
        )
        cores_per_socket = None
        sockets = None
        for line in output.splitlines():
            if 'Core(s) per socket:' in line:
                cores_per_socket = int(line.split(':')[1].strip())
            elif 'Socket(s):' in line:
                sockets = int(line.split(':')[1].strip())
        if cores_per_socket and sockets:
            return (cores_per_socket * sockets) // 2
    except Exception:
        pass
    # fallback: вернем логические ядра
    return (os.cpu_count() or 4) // 2

@lru_cache
def get_server_checksum_cmd():
    return checksum_cmds[platform.system().lower()]


# Получение списка файлов с сервера
def get_file_list(directory: str):
    command = f"find {directory} -type f".split(" ")
    output = exec_command(command)
    files_list = output.splitlines()
    files_sorted = sorted(files_list, key=os.path.getsize, reverse=True)
    return files_sorted


def calculate_one_file(file):
    checksum_cmd = get_server_checksum_cmd()
    sha256_cmd = [f"{checksum_cmd['sha256']}", f"{file}"]
    md5_cmd = [f"{checksum_cmd['md5']}", f"{file}"]
    split_number = checksum_cmd['split_number']
    errors = {}
    checksums = {}
    try:
        sha256_sum = exec_command(sha256_cmd).split()[split_number]
        md5_sum = exec_command(md5_cmd).split()[split_number]
        checksums[file] = {"sha256": sha256_sum, "md5": md5_sum}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        errors[file] = {
            "error": str(e)
        }
    return checksums, errors


# Получение контрольных сумм файлов
def get_checksums(files):
    checksums = {}
    errors = {}
    results = []
    with Pool(get_threads_count()) as pool:
        results.extend(pool.imap(calculate_one_file, files))
    for checksum, error in results:
        checksums.update(checksum)
        errors.update(error)
    return checksums, errors


# Запись результатов в файлы
def write_results(filename, data):
    os.makedirs(os.path.dirname(os.path.dirname(filename)), exist_ok=True)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(f"{filename}", "w", encoding="UTF-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def sign(results_without_sig):
    str_signature = json.dumps(results_without_sig, indent=4, ensure_ascii=False)
    signature = hashlib.sha3_512(str_signature.encode()).hexdigest()
    results = {
        "data": str_signature,
        "signature": signature
    }
    return results

def calc_checksums(group_name: str, path: str):
    start_timestamp =  str(int(datetime.now().timestamp()))
    start_time = datetime.now()
    files = get_file_list(path)
    checksums, errors = get_checksums(files)
    work_time = datetime.now() - start_time
    results_without_sig = {
        "checksums": checksums,
        "errors": errors,
        "files": files,
        "start_timestamp": start_timestamp,
        "work_time": work_time.total_seconds(),
        "group": group_name,
        "root_data": path,
    }
    results = sign(results_without_sig)
    write_results(f"{OUTPUT_DIRECTORY}/{group_name}/all_{start_timestamp}.json", results)


def main():
    for group in GROUPS:
        start_time_all = datetime.now()
        calc_checksums(group["name"], group["path"])
        print(f"{(datetime.now() - start_time_all)}")
    write_results(f"{OUTPUT_DIRECTORY}/groups.json", GROUPS)


if __name__ == "__main__":
    main()
