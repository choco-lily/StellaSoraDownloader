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


def get_server_info(server):
    """서버 정보를 미리 가져오는 함수"""
    try:
        headers = {"Authorization": make_auth(server)}
        cfg = get_json(f"{server['api']}/api/launcher/game/config", headers)
        data = cfg.get("data", {})
        ver = data.get("game_latest_version", "Unknown")
        path = data.get("game_latest_file_path", "")
        
        # manifest URL 가져오기
        if path:
            cfg2 = get_json(f"{server['api']}/api/launcher/game/config/json?version={ver}&file_path={path}", headers)
            manifest_url = cfg2.get("data", {}).get("url")
            
            if manifest_url:
                manifest = get_json(manifest_url)
                # 총 용량 계산
                total_size = 0
                for file_entry in manifest.get("file", []):
                    size_str = file_entry.get("size", "0")
                    try:
                        size_num = int(size_str)
                        total_size += size_num
                    except (ValueError, TypeError):
                        pass
                
                size_gb = total_size / (1024*1024*1024)
                filename = os.path.basename(path) if path else "Unknown"
                return f"{ver} - {filename} ({size_gb:.3f}GB)"
        
        filename = os.path.basename(path) if path else "Unknown"
        return f"{ver} - {filename} (Size unknown)"
    except Exception as e:
        return f"Error: {str(e)[:20]}..."

def select_server():
    print("Fetching server information...")
    server_info = {}
    
    for k, v in SERVERS.items():
        print(f"  Checking {v['name']}...")
        info = get_server_info(v)
        server_info[k] = info
    
    print("\nSelect a server:")
    for k, v in SERVERS.items():
        info = server_info.get(k, "Unknown")
        print(f" {k}. {v['name']} - {info}")
    
    choice = input("\nEnter server number (1-4, default=1): ").strip() or "1"
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
    print(f"\n[INFO] Selected server: {server['name']}")
    headers = {"Authorization": make_auth(server)}

    # 선택된 서버의 정보 다시 가져오기 (저장용)
    cfg = get_json(f"{server['api']}/api/launcher/game/config", headers)
    data = cfg.get("data", {})
    ver, path = data.get("game_latest_version"), data.get("game_latest_file_path")
    
    # cfg 응답 저장
    with open("cfg_response.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        
    cfg2 = get_json(f"{server['api']}/api/launcher/game/config/json?version={ver}&file_path={path}", headers)
    # cfg2 응답 저장
    with open("cfg2_response.json", "w", encoding="utf-8") as f:
        json.dump(cfg2, f, indent=2, ensure_ascii=False)
    manifest_url = cfg2.get("data", {}).get("url")

    manifest = get_json(manifest_url)
    
    # manifest 응답 저장
    with open("manifest_response.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    # file 배열의 size 값들을 숫자로 변환해서 합계 계산
    total_size = 0
    for file_entry in manifest.get("file", []):
        size_str = file_entry.get("size", "0")
        try:
            size_num = int(size_str)
            total_size += size_num
        except (ValueError, TypeError):
            print(f"[WARNING] Invalid size value: {size_str} for file: {file_entry.get('path', 'unknown')}")
    
    print(f"[INFO] Total download size: {total_size:,} bytes ({total_size / (1024*1024*1024):.3f} GB)")
    
    source = manifest["source"]
    out_dir = os.path.basename(source).lstrip("/")

    confirm = input("\nStart download? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("[INFO] Download cancelled.")
        return

    os.makedirs(out_dir, exist_ok=True)

    print(f"[INFO] Downloading {len(manifest['file'])} files to '{out_dir}'...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
        list(tqdm(exe.map(lambda e: download_file(server["pkg"], source, e, out_dir), manifest["file"]),
                  total=len(manifest["file"]), desc="Overall progress"))

    print("[INFO] All downloads completed successfully.")


if __name__ == "__main__":
    main()
