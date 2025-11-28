import argparse
import hashlib
import json
import os
import re
from datetime import datetime

import paramiko
from paramiko.client import SSHClient

from decorators import retry, lru_cache_custom
from config import SERVERS


def escape_filename(filename):
    return re.sub(r"([\\\s\"'()])", r"\\\1", filename)


# Подключение и выполнение команд на сервере
@retry()
def ssh_exec_command(server, command):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sock = get_jump(server)

    ssh.connect(
        server["host"],
        username=server["user"],
        key_filename=server["key_filename"],
        banner_timeout=600,
        auth_timeout=600,
        channel_timeout=3600,
        sock=sock
    )
    transport = ssh.get_transport()
    transport.set_keepalive(36000)
    stdin, stdout, stderr = ssh.exec_command(command)
    output = stdout.read().decode()
    ssh.close()
    return output


def get_jump(server):
    sock = None
    if jump := server.get("jump", None):
        jumpbox = SSHClient()
        jumpbox.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        jumpbox.connect(
            jump["host"],
            username=jump["user"],
            key_filename=jump["key_filename"],
            banner_timeout=600,
            auth_timeout=600,
            channel_timeout=3600,
        )
        jumpbox_transport = jumpbox.get_transport()
        src_addr = (jump["host"], 22)
        dest_addr = (server["host"], 22)
        sock = jumpbox_transport.open_channel("direct-tcpip", dest_addr, src_addr)
    return sock


# Поиск отсутствующих файлов
def find_lost_files(file_lists):
    all_files = set().union(*[set(files["checksums"].keys()) for files in file_lists.values()])
    lost_files = []

    for file in all_files:
        file_presence = {server["host"]: (file in file_lists[server["host"]]["files"]) for server in SERVERS}
        if not all(file_presence.values()):
            lost_files.append({"filename": file, **file_presence})

    return lost_files


# Поиск несовпадений контрольных сумм
def find_mismatch_sums(all_checksums):
    mismatch_sum = []
    all_files = set().union(*[set(files["checksums"].keys()) for files in all_checksums.values()])

    for file in all_files:
        file_checksums = {server["host"]: all_checksums[server["host"]]["checksums"].get(file, None) for server in SERVERS}
        if len(set(checksum["sha256"] for checksum in file_checksums.values() if checksum)) > 1 or \
                len(set(checksum["md5"] for checksum in file_checksums.values() if checksum)) > 1:
            file_checksums_readable = []
            for host, checksums in file_checksums.items():
                if not checksums:
                    file_checksums_readable.append({
                        "host": host,
                        "sums": None
                    })
                    continue
                file_checksums_readable.append({
                    "host": host,
                    "sums": {**checksums}
                })
            mismatch_sum.append({"filename": file, "info": file_checksums_readable})

    return mismatch_sum


# Запись результатов в файлы
def write_results(filename, data):
    fullname = f"./output/{filename}"
    os.makedirs(os.path.dirname(os.path.dirname(fullname)), exist_ok=True)
    os.makedirs(os.path.dirname(fullname), exist_ok=True)
    with open(fullname, "w", encoding="UTF-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def check_sign(data, signature):
    signature_calculated = hashlib.sha3_512(data.encode()).hexdigest()
    return signature_calculated == signature


@lru_cache_custom
def get_last_file_data(server, group_name: str, group_path: str):
    files_str = ssh_exec_command(server, f"find {server['path_to_output']}/{group_name} -type f").strip()
    files = files_str.split("\n")
    file_name = sorted(
        files,
        key=lambda name: int(name.split("_")[-1].split(".")[0])
    )[-1]
    data: dict = json.loads(
        ssh_exec_command(server, f"cat {file_name}").strip()
    )
    out_data = data["data"].replace(f"\"{group_path}", "\".")

    if check_sign(data["data"], data["signature"]):
        result = json.loads(out_data)
        result |= {k: v for k, v in data.items() if k != "data"}
        return result
    else:
        raise ValueError()


def do_lost_file(current_date=None, write=True):
    groups_set = {(group["name"], group["path"]) for server in SERVERS for group in server["groups"]}
    for group_name, path in groups_set:
        all_checksums = {}
        for server in SERVERS:
            files = get_last_file_data(server, group_name, path)
            all_checksums[server["host"]] = files

        lost_files = find_lost_files(all_checksums)
        if write and current_date:
            write_results(f"{group_name}/lost_files_{current_date}.json", lost_files)


def do_mismatch_sum(current_date=None, write=True):
    """
    Выполняет проверку на несовпадение контрольных сумм.

    :param current_date: Текущая дата для именования файла.
    :param write: Флаг для записи результатов в файл.
    """
    groups_set = {(group["name"], group["path"]) for server in SERVERS for group in server["groups"]}
    for group_name, path in groups_set:
        all_checksums = {}
        for server in SERVERS:
            if group_name not in {group["name"] for group in server["groups"]}:
                continue
            files = get_last_file_data(server, group_name, path)
            all_checksums[server["host"]] = files


        mismatch_sum = find_mismatch_sums(all_checksums)

        if write and current_date:
            write_results(f"{group_name}/mismatch_sum_{current_date}.json", mismatch_sum)


def do_check_execution_time():
    for server in SERVERS:
        for group in server["groups"]:
            files = get_last_file_data(server, group["name"], group["path"])
            work_time = files.get("work_time", None)
            if not work_time:
                continue
            print(
                f"{server['host']} (group: {group['name']}):"
                f" Work {work_time:.2f}s, {work_time/60:.2f}m, {work_time/3600:.2f}h"
            )


def set_groups():
    for server in SERVERS:
        groups_data_str = ssh_exec_command(server, f"cat {server['path_to_output']}/groups.json")
        groups = json.loads(groups_data_str)
        server["groups"] = groups


# Основной процесс
def main(is_check_lost: bool = True, is_check_sums: bool = True, is_check_duplicate: bool = True):
    current_date = datetime.now().strftime("%Y-%m-%d")
    set_groups()
    do_check_execution_time()
    if is_check_lost:
        do_lost_file(current_date)
    if is_check_sums:
        do_mismatch_sum(current_date)
    if is_check_duplicate:
        ...


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l", "--no_check_lost",
        action="store_false",
        default=True,
        help="Disable check for lost files"
    )
    parser.add_argument(
        "-s", "--no_check_sums",
        action="store_false",
        default=True,
        help="Disable check for sums"
    )
    parser.add_argument(
        "-d", "--no_check_duplicates",
        action="store_false",
        default=True,
        help="Disable check for duplicate files"
    )

    args = parser.parse_args()
    main(
        is_check_lost=args.no_check_lost,
        is_check_sums=args.no_check_sums,
        is_check_duplicate=args.no_check_duplicates,
    )
