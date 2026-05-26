import json
import hashlib
from pathlib import Path
from collections import defaultdict


def check_sign(data: str, signature: str) -> bool:
    signature_calculated = hashlib.sha3_512(data.encode()).hexdigest()
    return signature_calculated == signature


def find_changed_checksums(directory: str):
    """
    Проверяет все json-файлы в директории и ищет изменения checksum одного и того же файла во времени.
    """

    directory = Path(directory)

    # структура:
    # {
    #   filepath: [
    #       {
    #           timestamp: int,
    #           sha256: str,
    #           md5: str,
    #           source_file: str
    #       }
    #   ]
    # }
    files_history = defaultdict(list)

    invalid_signatures = []

    for json_file in sorted(directory.rglob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                raw = json.load(f)

            data_str = raw["data"]
            signature = raw["signature"]

            # Проверка подписи
            if not check_sign(data_str, signature):
                invalid_signatures.append(str(json_file))
                continue

            data = json.loads(data_str)

            timestamp = int(data.get("start_timestamp", 0))

            for filepath, sums in data.get("checksums", {}).items():
                files_history[filepath].append({
                    "timestamp": timestamp,
                    "sha256": sums.get("sha256"),
                    "md5": sums.get("md5"),
                    "source_file": str(json_file)
                })

        except Exception as e:
            print(f"Ошибка обработки {json_file}: {e}")

    changed_files = []

    for filepath, history in files_history.items():
        history = sorted(history, key=lambda x: x["timestamp"])

        previous = None

        for item in history:
            current_sums = (
                item["sha256"],
                item["md5"]
            )

            if previous is not None:
                previous_sums = (
                    previous["sha256"],
                    previous["md5"]
                )

                if current_sums != previous_sums:
                    changed_files.append({
                        "file": filepath,
                        "old_timestamp": previous["timestamp"],
                        "new_timestamp": item["timestamp"],
                        "old_sha256": previous["sha256"],
                        "new_sha256": item["sha256"],
                        "old_md5": previous["md5"],
                        "new_md5": item["md5"],
                        "old_source": previous["source_file"],
                        "new_source": item["source_file"],
                    })

            previous = item

    return {
        "changed_files": changed_files,
        "invalid_signatures": invalid_signatures
    }


if __name__ == "__main__":
    dirs = [
        "./output/games", "./output/documents_backup", "./output/new_data",
        "./output/old_data", "./output/phones", "./output/proxmox_backup",
        "./output/some_unix_soft"
    ]
    for dir_ in dirs:
        print(dir_)
        result = find_changed_checksums(dir_)

        print("Файлы с изменившимися checksum:\n")

        for item in result["changed_files"]:
            print(
                f"{item['file']}\n"
                f"  OLD: {item['old_timestamp']} {item['old_sha256']}\n"
                f"  NEW: {item['new_timestamp']} {item['new_sha256']}\n"
            )

        print("\nФайлы с битой подписью:\n")

        for file in result["invalid_signatures"]:
            print(file)
