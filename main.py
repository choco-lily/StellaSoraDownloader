import hashlib, json, time, requests, urllib3, os, concurrent.futures
from tqdm import tqdm

urllib3.disable_warnings()

# Disable any leftover proxy settings
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ[k] = ""

SALT = "DE7108E9B2842FD460F4777702727869"
SALT_CN = "872550AD59A235662C5B7D5F88CEBE4B"

SERVERS = {
    "1": {"name": "Korea (KR)", "api": "https://api-launcher-kr.yo-star.com", "pkg": "https://launcher-pkg-ss-kr.yo-star.com", "tag": "StellaSora_KR", "salt": SALT},
    "2": {"name": "Japan (JP)", "api": "https://api-launcher-jp.yo-star.com", "pkg": "https://launcher-pkg-ss-jp.yo-star.com", "tag": "StellaSora_JP", "salt": SALT},
    "3": {"name": "Global (EN)", "api": "https://api-launcher-en.yo-star.com", "pkg": "https://launcher-pkg-ss-en.yo-star.com", "tag": "StellaSora_EN", "salt": SALT},
    "4": {"name": "China (CN)", "api": "https://launcher-api.yostar.net", "pkg": "https://game-launcher-ss-cn.yostar.net", "tag": "StellaSora_CN", "salt": SALT_CN},
}

LAUNCHER_VERSION = "1.6.0"


def select_server():
    print("Select a server:")
    for k, v in SERVERS.items():
        print(f" {k}. {v['name']}")
    choice = input("Enter server number (1-4, default=1): ").strip() or "1"
    return SERVERS.get(choice, SERVERS["1"])


def make_auth(server, data=""):
    head = {"game_tag": server["tag"], "time": int(time.time()), "version": LAUNCHER_VERSION}
    sign_str = json.dumps(head, separators=(',', ':')) + data + server["salt"]
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    return json.dumps({"head": head, "sign": sign}, separators=(',', ':'))


def get_json(url, headers=None):
    r = requests.get(url, headers=headers, verify=False, timeout=15)
    r.raise_for_status()
    return r.json()


def download_file(pkg_url, source, entry, out_dir):
    url = pkg_url + source + entry["path"]
    local_path = os.path.join(out_dir, entry["path"].lstrip("/"))
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        r = requests.get(url, stream=True, verify=False, timeout=30)
        r.raise_for_status()
        total = int(entry.get("size", 0)) or None
        with open(local_path, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc=entry["path"], leave=False
        ) as pbar:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
        return True
    except Exception as e:
        print(f"[ERROR] {entry['path']}: {e}")
        return False


def main():
    server = select_server()
    print(f"[INFO] Selected server: {server['name']}")
    headers = {"Authorization": make_auth(server)}

    cfg = get_json(f"{server['api']}/api/launcher/game/config", headers)
    data = cfg.get("data", {})
    ver, path = data.get("game_latest_version"), data.get("game_latest_file_path")
    print(f"[INFO] Latest version: {ver}\n[INFO] File path: {path}")

    cfg2 = get_json(f"{server['api']}/api/launcher/game/config/json?version={ver}&file_path={path}", headers)
    manifest_url = cfg2.get("data", {}).get("url")
    print(f"[INFO] Manifest URL: {manifest_url}")

    manifest = get_json(manifest_url)
    source = manifest["source"]
    out_dir = os.path.basename(source).lstrip("/")
    os.makedirs(out_dir, exist_ok=True)

    print(f"[INFO] Downloading {len(manifest['file'])} files to '{out_dir}'...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
        list(tqdm(exe.map(lambda e: download_file(server["pkg"], source, e, out_dir), manifest["file"]),
                  total=len(manifest["file"]), desc="Overall progress"))

    print("[INFO] All downloads completed successfully.")


if __name__ == "__main__":
    main()
