import hashlib, json, time, requests, urllib3, os, concurrent.futures
from tqdm import tqdm
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading

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
    "5": {"name": "TaiWan (TW)", "api": "https://api-launcher-tw.stargazer-games.com", "pkg": "https://launcher-pkg-ss-hk.stargazer-games.com", "tag": "StellaSora_TW", "salt": SALT},
}

LAUNCHER_VERSION = "1.6.0"


def create_server_size_folder(server_name, total_size_kb):
    """서버별 폴더 안에 용량(KB) 폴더를 생성하고 경로를 반환"""
    server_folder = os.path.join(server_name)
    size_folder = os.path.join(server_folder, f"{total_size_kb}")
    os.makedirs(size_folder, exist_ok=True)
    return size_folder


def find_existing_folders(server_name):
    """기존에 저장된 폴더들을 찾아서 반환 (생성 시간 순으로 정렬)"""
    existing_folders = []
    if os.path.exists(server_name):
        for item in os.listdir(server_name):
            item_path = os.path.join(server_name, item)
            if os.path.isdir(item_path):
                # 폴더 이름이 숫자인지 확인 (용량KB)
                try:
                    size_kb = int(item)
                    # 폴더 생성 시간 가져오기
                    creation_time = os.path.getctime(item_path)
                    existing_folders.append((size_kb, item_path, creation_time))
                except ValueError:
                    continue
    # 생성 시간 순으로 정렬 (최신이 마지막)
    return sorted(existing_folders, key=lambda x: x[2])


def compare_file_changes(old_manifest, new_manifest):
    """파일 변경사항을 비교하여 반환"""
    old_files = {file_entry["path"]: file_entry for file_entry in old_manifest.get("file", [])}
    new_files = {file_entry["path"]: file_entry for file_entry in new_manifest.get("file", [])}
    
    # 파일 변경사항 분석
    added_files = []
    removed_files = []
    changed_files = []
    
    # 새로 추가된 파일들
    for path, file_entry in new_files.items():
        if path not in old_files:
            added_files.append({
                "path": path,
                "size": int(file_entry.get("size", 0)),
                "hash": file_entry.get("hash", "")
            })
    
    # 삭제된 파일들
    for path, file_entry in old_files.items():
        if path not in new_files:
            removed_files.append({
                "path": path,
                "size": int(file_entry.get("size", 0)),
                "hash": file_entry.get("hash", "")
            })
    
    # 변경된 파일들 (해시가 다른 파일들)
    for path, new_file_entry in new_files.items():
        if path in old_files:
            old_file_entry = old_files[path]
            if old_file_entry.get("hash") != new_file_entry.get("hash"):
                changed_files.append({
                    "path": path,
                    "old_size": int(old_file_entry.get("size", 0)),
                    "new_size": int(new_file_entry.get("size", 0)),
                    "old_hash": old_file_entry.get("hash", ""),
                    "new_hash": new_file_entry.get("hash", "")
                })
    
    return {
        "added": added_files,
        "removed": removed_files,
        "changed": changed_files
    }


def compare_with_existing(server_name, new_cfg, new_cfg2, new_manifest, new_size_kb):
    """새로 받은 응답과 기존 저장된 응답들을 비교"""
    existing_folders = find_existing_folders(server_name)
    
    if not existing_folders:
        return None
    
    # 가장 최근 폴더 찾기 (생성 시간 기준)
    latest_folder = existing_folders[-1]
    latest_size_kb, latest_path, latest_time = latest_folder
    
    if latest_size_kb == new_size_kb:
        return None
    
    # 기존 파일들 로드
    try:
        config_path = os.path.join(latest_path, f"config_{server_name}.json")
        config2_path = os.path.join(latest_path, f"config2_{server_name}.json")
        manifest_path = os.path.join(latest_path, f"manifest_{server_name}.json")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            old_cfg = json.load(f)
        with open(config2_path, 'r', encoding='utf-8') as f:
            old_cfg2 = json.load(f)
        with open(manifest_path, 'r', encoding='utf-8') as f:
            old_manifest = json.load(f)
        
        # 파일 변경사항 상세 분석
        file_changes = compare_file_changes(old_manifest, new_manifest)
        
        # 파일 수 비교 (출력하지 않고 데이터만 수집)
        old_file_count = len(old_manifest.get("file", []))
        new_file_count = len(new_manifest.get("file", []))
        
        # 버전 정보 수집
        old_ver = old_cfg.get("data", {}).get("game_latest_version", "Unknown")
        new_ver = new_cfg.get("data", {}).get("game_latest_version", "Unknown")
        
        return {
            "old_size_kb": latest_size_kb,
            "new_size_kb": new_size_kb,
            "old_version": old_ver,
            "new_version": new_ver,
            "old_file_count": old_file_count,
            "new_file_count": new_file_count,
            "old_folder": latest_path,
            "new_folder": None,  # 아직 저장되지 않음
            "file_changes": file_changes
        }
        
    except Exception as e:
        return None


def save_server_request(server_name, request_type, data, date_folder):
    """서버별 요청 데이터를 날짜별 폴더에 저장"""
    filename = f"{request_type}_{server_name}.json"
    filepath = os.path.join(date_folder, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_server_info(server, date_folder=None):
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
                
                size_kb = total_size / 1024
                filename = os.path.basename(path) if path else "Unknown"
                file_basename = os.path.splitext(filename)[0]  # 확장자 제거
                total_size_kb_int = int(total_size / 1024)  # KB로 변환 (정수)
                
                # 기존 데이터와 비교
                diff_info = compare_with_existing(file_basename, cfg, cfg2, manifest, total_size_kb_int)
                
                # 요청값 저장 (파일명 기반)
                if date_folder:
                    server_size_folder = create_server_size_folder(file_basename, total_size_kb_int)
                    save_server_request(file_basename, "config", cfg, server_size_folder)
                    save_server_request(file_basename, "config2", cfg2, server_size_folder)
                    save_server_request(file_basename, "manifest", manifest, server_size_folder)
                    
                    # diff 정보가 있으면 새 폴더 경로 업데이트
                    if diff_info:
                        diff_info["new_folder"] = server_size_folder
                
                return f"{ver} - {filename} ({size_kb:.0f}KB)", cfg, cfg2, manifest, diff_info
        
        filename = os.path.basename(path) if path else "Unknown"
        return f"{ver} - {filename} (Size unknown)", None, None, None, None
    except Exception as e:
        return f"Error: {str(e)[:20]}...", None, None, None, None

def select_server():
    print("Fetching server information...")
    server_info = {}
    server_data = {}
    diff_summary = []
    
    print(f"[INFO] Saving request data to server-specific size(KB) folders.")
    
    for k, v in SERVERS.items():
        print(f"  Checking {v['name']}...")
        info, cfg, cfg2, manifest, diff_info = get_server_info(v, True)  # 저장 활성화
        server_info[k] = info
        server_data[k] = {"cfg": cfg, "cfg2": cfg2, "manifest": manifest}
        
        # diff 정보가 있으면 요약에 추가
        if diff_info:
            diff_summary.append({
                "server": v['name'],
                "old_size": diff_info["old_size_kb"],
                "new_size": diff_info["new_size_kb"],
                "old_version": diff_info["old_version"],
                "new_version": diff_info["new_version"],
                "old_files": diff_info["old_file_count"],
                "new_files": diff_info["new_file_count"],
                "file_changes": diff_info.get("file_changes", {})
            })
    
    print("\nSelect a server:")
    for k, v in SERVERS.items():
        info = server_info.get(k, "Unknown")
        print(f" {k}. {v['name']} - {info}")
    
    # diff 요약 출력
    if diff_summary:
        print(f"\n[DIFF SUMMARY] 변경사항 감지:")
        for diff in diff_summary:
            size_diff = diff["new_size"] - diff["old_size"]
            file_diff = diff["new_files"] - diff["old_files"]
            print(f"  {diff['server']}:")
            print(f"    용량: {diff['old_size']}KB → {diff['new_size']}KB ({size_diff:+d}KB)")
            print(f"    버전: {diff['old_version']} → {diff['new_version']}")
            print(f"    파일: {diff['old_files']}개 → {diff['new_files']}개 ({file_diff:+d}개)")
    
    choice = input("\nEnter server number (1-4, default=1): ").strip() or "1"
    selected_server = SERVERS.get(choice, SERVERS["1"])
    selected_data = server_data.get(choice)
    
    return selected_server, selected_data


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
    except KeyboardInterrupt:
        print("[INFO] Download cancelled by user")
        return False
    except Exception as e:
        print(f"[ERROR] {entry['path']}: {e}")
        return False


def main():
    server, server_data = select_server()
    print(f"\n[INFO] Selected server: {server['name']}")
    
    # 저장된 데이터 재사용
    cfg = server_data["cfg"]
    cfg2 = server_data["cfg2"]
    manifest = server_data["manifest"]
    
    data = cfg.get("data", {})
    ver, path = data.get("game_latest_version"), data.get("game_latest_file_path")
    
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


class FileDownloaderGUI:
    def __init__(self, server, manifest, server_pkg_url, source):
        self.server = server
        self.manifest = manifest
        self.server_pkg_url = server_pkg_url
        self.source = source
        self.selected_files = []
        
        self.root = tk.Tk()
        self.root.title(f"StellaSora Downloader - {server['name']}")
        self.root.geometry("1000x700")
        
        self.setup_ui()
        
    def setup_ui(self):
        # 상단 프레임
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 서버 정보
        ttk.Label(top_frame, text=f"Server: {self.server['name']}", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        # 파일 개수 및 총 용량
        total_files = len(self.manifest.get("file", []))
        total_size = sum(int(f.get("size", 0)) for f in self.manifest.get("file", []))
        total_size_mb = total_size / (1024 * 1024)
        
        ttk.Label(top_frame, text=f"Total Files: {total_files} | Total Size: {total_size_mb:.0f}MB").pack(anchor=tk.W)
        
        # 버튼 프레임
        button_frame = ttk.Frame(top_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Deselect All", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Download Selected", command=self.download_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Download All", command=self.download_all).pack(side=tk.LEFT, padx=5)
        
        # 검색 프레임
        search_frame = ttk.Frame(top_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 키보드 입력 이벤트 바인딩
        search_entry.bind("<KeyRelease>", self.on_search_key)
        
        # 검색 결과 표시 라벨
        self.search_result_label = ttk.Label(search_frame, text="", foreground="gray")
        self.search_result_label.pack(side=tk.RIGHT, padx=5)
        
        # 파일 리스트 프레임
        list_frame = ttk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 트리뷰 생성 (체크박스 방식)
        columns = ("File", "Size", "Hash", "Selected")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
        
        # 컬럼 설정
        self.tree.heading("File", text="File Path")
        self.tree.heading("Size", text="Size")
        self.tree.heading("Hash", text="Hash")
        self.tree.heading("Selected", text="Selected")
        
        # 컬럼 크기를 내용에 맞게 자동 조정
        self.tree.column("File", width=400, minwidth=200)
        self.tree.column("Size", width=80, minwidth=65)
        self.tree.column("Hash", width=150, minwidth=150)
        self.tree.column("Selected", width=80, minwidth=60)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 파일 클릭 이벤트 (체크박스 방식)
        self.tree.bind("<Button-1>", self.toggle_selection)
        self.tree.bind("<B1-Motion>", self.drag_selection)
        
        # 드래그 시작 상태 저장
        self.drag_start_state = None
        self.drag_start_item = None
        
        # 파일 목록 로드
        self.load_files()
        
    def load_files(self):
        for file_entry in self.manifest.get("file", []):
            file_path = file_entry.get("path", "")
            size_bytes = int(file_entry.get("size", 0))
            size_kb = size_bytes / 1024
            file_hash = file_entry.get("hash", "N/A")
            
            self.tree.insert("", tk.END, values=(file_path, f"{size_kb:.0f}KB", file_hash, "☐"))
            
    def refresh_file_list(self):
        """파일 목록 새로고침 (검색어 유지)"""
        search_term = self.search_var.get().lower()
        
        # 모든 항목 삭제
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 필터링된 항목만 추가
        filtered_count = 0
        total_count = len(self.manifest.get("file", []))
        
        for file_entry in self.manifest.get("file", []):
            file_path = file_entry.get("path", "")
            
            # 검색어가 비어있으면 모든 파일 표시, 아니면 검색어가 포함된 파일만 표시
            if not search_term or search_term in file_path.lower():
                size_bytes = int(file_entry.get("size", 0))
                size_kb = size_bytes / 1024
                file_hash = file_entry.get("hash", "N/A")
                
                # 선택 상태 확인
                is_selected = file_path in self.selected_files
                checkbox = "☑" if is_selected else "☐"
                
                self.tree.insert("", tk.END, values=(file_path, f"{size_kb:.0f}KB", file_hash, checkbox))
                filtered_count += 1
        
        # 검색 결과 표시
        if search_term:
            self.search_result_label.config(text=f"{filtered_count}/{total_count} files")
        else:
            self.search_result_label.config(text=f"{total_count} files")
    
    def on_search_key(self, event):
        """키보드 입력 이벤트 핸들러"""
        # 이벤트 위젯에서 직접 값 가져오기
        search_text = event.widget.get()
        
        # StringVar 업데이트
        self.search_var.set(search_text)
        
        # 파일 목록 새로고침
        self.refresh_file_list()
                
    def toggle_selection(self, event):
        """체크박스 토글 선택"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
            
        values = self.tree.item(item, "values")
        file_path = values[0]
        size = values[1]
        file_hash = values[2]
        
        # 드래그 시작 상태 저장 (체크박스 상태)
        checkbox_state = values[3]
        self.drag_start_state = checkbox_state
        self.drag_start_item = item
        
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self.tree.item(item, values=(file_path, size, file_hash, "☐"))
        else:
            self.selected_files.append(file_path)
            self.tree.item(item, values=(file_path, size, file_hash, "☑"))
            
    def drag_selection(self, event):
        """드래그 선택 - 시작 상태에 따라 동작 결정 (범위 처리)"""
        if not hasattr(self, 'drag_start_state') or self.drag_start_state is None or not self.drag_start_item:
            return
            
        item = self.tree.identify_row(event.y)
        if not item:
            return
            
        # 드래그 범위 계산
        start_idx = self.tree.index(self.drag_start_item)
        end_idx = self.tree.index(item)
        
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
            
        # 범위 내 모든 항목 처리
        for i in range(start_idx, end_idx + 1):
            child = self.tree.get_children()[i]
            values = self.tree.item(child, "values")
            file_path = values[0]
            size = values[1]
            file_hash = values[2]
            
            # 시작 상태에 따라 동작 결정
            if self.drag_start_state == "☑":
                # 시작이 체크된 상태면 → 모든 항목을 체크 해제
                if file_path in self.selected_files:
                    self.selected_files.remove(file_path)
                    self.tree.item(child, values=(file_path, size, file_hash, "☐"))
            else:
                # 시작이 체크 해제된 상태면 → 모든 항목을 체크
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
                    self.tree.item(child, values=(file_path, size, file_hash, "☑"))
    
    def select_all(self):
        """모든 파일 선택 (체크박스 방식)"""
        self.selected_files = []
        for file_entry in self.manifest.get("file", []):
            file_path = file_entry.get("path", "")
            self.selected_files.append(file_path)
        self.refresh_file_list()
        
    def deselect_all(self):
        """모든 파일 선택 해제 (체크박스 방식)"""
        self.selected_files = []
        self.refresh_file_list()
        
    def download_selected(self):
        if not self.selected_files:
            messagebox.showwarning("Warning", "Please select files to download.")
            return
            
        # 다운로드 폴더 선택
        download_dir = filedialog.askdirectory(title="Select Download Directory")
        if not download_dir:
            return
            
        # 선택된 파일만 다운로드
        selected_entries = []
        for file_entry in self.manifest.get("file", []):
            if file_entry.get("path", "") in self.selected_files:
                selected_entries.append(file_entry)
                
        self.start_download(selected_entries, download_dir)
        
    def download_all(self):
        # 다운로드 폴더 선택
        download_dir = filedialog.askdirectory(title="Select Download Directory")
        if not download_dir:
            return
            
        # 모든 파일 다운로드
        self.start_download(self.manifest.get("file", []), download_dir)
        
    def start_download(self, file_entries, download_dir):
        # 다운로드 진행 상황을 보여주는 새 창 생성
        self.download_window = tk.Toplevel(self.root)
        self.download_window.title("Download Progress")
        self.download_window.geometry("600x400")
        self.download_window.resizable(False, False)
        
        # 진행 상황 프레임
        progress_frame = ttk.Frame(self.download_window)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 전체 진행률
        ttk.Label(progress_frame, text="Overall Progress:", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        self.overall_progress = ttk.Progressbar(progress_frame, length=500, mode='determinate')
        self.overall_progress.pack(fill=tk.X, pady=5)
        
        self.overall_label = ttk.Label(progress_frame, text="0 / 0 files")
        self.overall_label.pack(anchor=tk.W)
        
        # 현재 다운로드 중인 파일
        ttk.Label(progress_frame, text="Current File:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(20, 5))
        
        self.current_file_label = ttk.Label(progress_frame, text="Preparing...", wraplength=550)
        self.current_file_label.pack(anchor=tk.W)
        
        self.current_progress = ttk.Progressbar(progress_frame, length=500, mode='determinate')
        self.current_progress.pack(fill=tk.X, pady=5)
        
        self.current_speed_label = ttk.Label(progress_frame, text="Speed: 0 MB/s")
        self.current_speed_label.pack(anchor=tk.W)
        
        # 로그 텍스트
        ttk.Label(progress_frame, text="Download Log:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(20, 5))
        
        log_frame = ttk.Frame(progress_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 다운로드 시작
        self.download_files(file_entries, download_dir)
        
    def download_files(self, file_entries, download_dir):
        self.log_message(f"Starting download of {len(file_entries)} files to '{download_dir}'")
        
        # 전체 진행률 설정
        self.overall_progress['maximum'] = len(file_entries)
        self.overall_progress['value'] = 0
        
        completed_files = 0
        
        for i, file_entry in enumerate(file_entries):
            file_path = file_entry.get("path", "")
            self.current_file_label.config(text=f"Downloading: {file_path}")
            self.log_message(f"[{i+1}/{len(file_entries)}] Starting: {file_path}")
            
            try:
                # 파일 다운로드
                success = self.download_single_file(file_entry, download_dir)
                
                if success:
                    completed_files += 1
                    self.log_message(f"[{i+1}/{len(file_entries)}] Completed: {file_path}")
                else:
                    self.log_message(f"[{i+1}/{len(file_entries)}] Failed: {file_path}")
                    
            except Exception as e:
                self.log_message(f"[{i+1}/{len(file_entries)}] Error: {file_path} - {str(e)}")
            
            # 진행률 업데이트
            self.overall_progress['value'] = i + 1
            self.overall_label.config(text=f"{i + 1} / {len(file_entries)} files")
            self.download_window.update()
        
        self.log_message(f"Download completed! {completed_files}/{len(file_entries)} files downloaded successfully.")
        self.current_file_label.config(text="Download completed!")
        
    def download_single_file(self, file_entry, download_dir):
        url = self.server_pkg_url + self.source + file_entry["path"]
        local_path = os.path.join(download_dir, file_entry["path"].lstrip("/"))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        try:
            r = requests.get(url, stream=True, verify=False, timeout=30)
            r.raise_for_status()
            
            total_size = int(file_entry.get("size", 0)) or None
            downloaded_size = 0
            
            self.current_progress['maximum'] = total_size or 100
            self.current_progress['value'] = 0
            
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 현재 파일 진행률 업데이트
                        if total_size:
                            self.current_progress['value'] = downloaded_size
                            speed_mb = (downloaded_size / (1024 * 1024)) / max(1, (time.time() - getattr(self, 'start_time', time.time())))
                            self.current_speed_label.config(text=f"Speed: {speed_mb:.2f} MB/s")
                        
                        self.download_window.update()
            
            return True
            
        except Exception as e:
            self.log_message(f"Error downloading {file_entry['path']}: {str(e)}")
            return False
            
    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.download_window.update()
        
    def run(self):
        self.root.mainloop()


class ServerSelectorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("StellaSora Downloader - Server Selection")
        self.root.geometry("600x500")
        
        self.server_data = {}
        self.reference_server = None  # 기준 서버 속성 초기화
        self.setup_ui()
        
    def setup_ui(self):
        # 상단 프레임
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="StellaSora Downloader", font=("Arial", 16, "bold")).pack()
        ttk.Label(top_frame, text="Select a server to download from:", font=("Arial", 12)).pack(pady=5)
        
        # 서버 목록 프레임
        server_frame = ttk.Frame(self.root)
        server_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 서버 리스트박스
        self.server_listbox = tk.Listbox(server_frame, font=("Arial", 11), height=4)
        scrollbar = ttk.Scrollbar(server_frame, orient=tk.VERTICAL, command=self.server_listbox.yview)
        self.server_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.server_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 더블클릭 이벤트
        self.server_listbox.bind("<Double-1>", self.select_server)
        
        # 하단 버튼 프레임
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Refresh Server List", command=self.refresh_servers).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Compare Servers", command=self.compare_servers).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Select Server", command=self.select_server).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(side=tk.RIGHT, padx=5)
        
        # 상태 표시
        self.status_label = ttk.Label(self.root, text="Loading server information...", font=("Arial", 10))
        self.status_label.pack(pady=5)
        
        # 서버 정보 로드
        self.refresh_servers()
        
    def refresh_servers(self):
        # 버튼 비활성화
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button):
                        child.config(state='disabled')
        
        self.status_label.config(text="Fetching server information...")
        self.root.update()
        
        # 진행 상황 표시
        self.progress_label = ttk.Label(self.root, text="", font=("Arial", 10))
        self.progress_label.pack(pady=2)
        
        # 백그라운드에서 서버 정보 가져오기
        thread = threading.Thread(target=self.fetch_servers_background)
        thread.daemon = True
        thread.start()
        
    def fetch_servers_background(self):
        self.server_listbox.delete(0, tk.END)
        self.server_data = {}
        
        total_servers = len(SERVERS)
        
        for i, (k, v) in enumerate(SERVERS.items()):
            try:
                # 현재 서버 정보 업데이트
                self.root.after(0, lambda s=v['name']: self.progress_label.config(text=f"Checking {s}..."))
                
                info, cfg, cfg2, manifest, diff_info = get_server_info(v, True)
                self.server_data[k] = {
                    "server": v,
                    "info": info,
                    "cfg": cfg,
                    "cfg2": cfg2,
                    "manifest": manifest,
                    "diff_info": diff_info
                }
                
                # diff 정보가 있으면 즉시 표시
                if diff_info:
                    diff_summary = [{
                        "server": v['name'],
                        "old_size": diff_info["old_size_kb"],
                        "new_size": diff_info["new_size_kb"],
                        "old_version": diff_info["old_version"],
                        "new_version": diff_info["new_version"],
                        "old_files": diff_info["old_file_count"],
                        "new_files": diff_info["new_file_count"],
                        "file_changes": diff_info.get("file_changes", {}),
                        "server_config": v,  # 서버 설정 정보 추가
                        "manifest": manifest  # manifest 정보 추가
                    }]
                    # 즉시 diff 창 표시
                    self.root.after(0, lambda summary=diff_summary: self.show_diff_summary(summary))
                
                # 서버 정보를 리스트박스에 추가
                self.root.after(0, lambda k=k, v=v, info=info: self.server_listbox.insert(tk.END, f"{k}. {v['name']} - {info}"))
                
            except Exception as e:
                error_msg = f"{k}. {v['name']} - Error: {str(e)[:30]}..."
                self.root.after(0, lambda msg=error_msg: self.server_listbox.insert(tk.END, msg))
                
            # 진행률 업데이트
            progress = f"Progress: {i+1}/{total_servers} servers checked"
            self.root.after(0, lambda p=progress: self.progress_label.config(text=p))
        
        # 완료 후 UI 업데이트
        self.root.after(0, self.refresh_complete)
        
    def refresh_complete(self):
        self.status_label.config(text=f"Found {len(self.server_data)} servers")
        self.progress_label.config(text="Server information loaded successfully!")
        
        # 버튼 다시 활성화
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button):
                        child.config(state='normal')
    
    def show_diff_summary(self, diff_summary):
        """diff 요약을 별도 창으로 표시"""
        server_name = diff_summary[0]['server'] if diff_summary else "Unknown"
        diff_window = tk.Toplevel(self.root)
        diff_window.title(f"Update Summary - {server_name}")
        diff_window.geometry("1000x700")
        
        # 서버 정보 저장 (다운로드용)
        diff_window.server_config = diff_summary[0]['server_config']
        diff_window.manifest = diff_summary[0]['manifest']
        
        # 메인 프레임
        main_frame = ttk.Frame(diff_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        ttk.Label(main_frame, text=f"🔄 {server_name} Update Summary", font=("Arial", 14, "bold")).pack(pady=10)
        
        # 서버 기본 정보
        info_frame = ttk.LabelFrame(main_frame, text="Server Information", padding=10)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        diff = diff_summary[0]  # 단일 서버 정보
        size_diff = diff["new_size"] - diff["old_size"]
        file_diff = diff["new_files"] - diff["old_files"]
        
        ttk.Label(info_frame, text=f"Size: {diff['old_size']:,}KB → {diff['new_size']:,}KB ({size_diff:+d}KB)", font=("Arial", 10)).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Version: {diff['old_version']} → {diff['new_version']}", font=("Arial", 10)).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Files: {diff['old_files']:,} → {diff['new_files']:,} ({file_diff:+d})", font=("Arial", 10)).pack(anchor=tk.W)
        
        # 파일 변경사항이 있으면 상세 표시
        if "file_changes" in diff and diff["file_changes"]:
            file_changes = diff["file_changes"]
            
            # 추가된 파일들
            if file_changes["added"]:
                self.create_file_list_frame(main_frame, "➕ Added Files", file_changes["added"], "added")
            
            # 삭제된 파일들
            if file_changes["removed"]:
                self.create_file_list_frame(main_frame, "➖ Removed Files", file_changes["removed"], "removed")
            
            # 변경된 파일들
            if file_changes["changed"]:
                self.create_file_list_frame(main_frame, "🔄 Changed Files", file_changes["changed"], "changed")
        
        # 닫기 버튼
        ttk.Button(main_frame, text="Close", command=diff_window.destroy).pack(pady=10)
    
    def create_file_list_frame(self, parent, title, files, change_type):
        """파일 목록을 표시하는 프레임 생성"""
        frame = ttk.LabelFrame(parent, text=title, padding=5)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 상단 버튼 프레임
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(button_frame, text="Select All", command=lambda: self.select_all_files(tree)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Deselect All", command=lambda: self.deselect_all_files(tree)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Download Selected", command=lambda: self.download_selected_files(tree, change_type)).pack(side=tk.LEFT, padx=(0, 5))
        
        # Treeview 생성
        columns = ("Select", "File", "Size", "Hash", "Change")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=8)
        
        # 컬럼 설정
        tree.heading("Select", text="☑")
        tree.heading("File", text="File Path")
        tree.heading("Size", text="Size")
        tree.heading("Hash", text="Hash")
        tree.heading("Change", text="Change")
        
        tree.column("Select", width=50, anchor=tk.CENTER)
        tree.column("File", width=300, anchor=tk.W)
        tree.column("Size", width=120, anchor=tk.E)
        tree.column("Hash", width=120, anchor=tk.W)
        tree.column("Change", width=80, anchor=tk.E)
        
        # 체크박스 클릭 이벤트
        tree.bind("<Button-1>", lambda e: self.toggle_file_selection(tree, e))
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 파일 데이터 추가
        for file_info in files:
            if change_type == "added":
                size_kb = file_info["size"] / 1024
                hash_short = file_info["hash"][:16] if file_info["hash"] else "N/A"
                tree.insert("", tk.END, values=(
                    "☐",  # 체크박스
                    file_info["path"],
                    f"{size_kb:.1f}KB",
                    hash_short,
                    "+"
                ))
            elif change_type == "removed":
                size_kb = file_info["size"] / 1024
                hash_short = file_info["hash"][:16] if file_info["hash"] else "N/A"
                tree.insert("", tk.END, values=(
                    "☐",  # 체크박스
                    file_info["path"],
                    f"{size_kb:.1f}KB",
                    hash_short,
                    "-"
                ))
            elif change_type == "changed":
                size_diff = file_info["new_size"] - file_info["old_size"]
                old_size_kb = file_info["old_size"] / 1024
                new_size_kb = file_info["new_size"] / 1024
                old_hash_short = file_info["old_hash"][:8] if file_info["old_hash"] else "N/A"
                new_hash_short = file_info["new_hash"][:8] if file_info["new_hash"] else "N/A"
                tree.insert("", tk.END, values=(
                    "☐",  # 체크박스
                    file_info["path"],
                    f"{old_size_kb:.1f}KB → {new_size_kb:.1f}KB",
                    f"{old_hash_short}→{new_hash_short}",
                    f"{size_diff:+d}B"
                ))
        
        # 요약 정보 표시
        if files:
            total_count = len(files)
            if change_type == "added":
                total_size = sum(f["size"] for f in files)
                summary_text = f"Total: {total_count} files, {total_size/1024:.1f}KB"
            elif change_type == "removed":
                total_size = sum(f["size"] for f in files)
                summary_text = f"Total: {total_count} files, {total_size/1024:.1f}KB"
            elif change_type == "changed":
                total_size_diff = sum(f["new_size"] - f["old_size"] for f in files)
                summary_text = f"Total: {total_count} files, {total_size_diff/1024:+.1f}KB"
            
            ttk.Label(frame, text=summary_text, font=("Arial", 9, "italic")).pack(pady=2)
        
        return tree
    
    def toggle_file_selection(self, tree, event):
        """파일 선택 토글"""
        item = tree.identify_row(event.y)
        if item:
            values = list(tree.item(item, "values"))
            if values[0] == "☐":
                values[0] = "☑"
            else:
                values[0] = "☐"
            tree.item(item, values=values)
    
    def select_all_files(self, tree):
        """모든 파일 선택"""
        for item in tree.get_children():
            values = list(tree.item(item, "values"))
            values[0] = "☑"
            tree.item(item, values=values)
    
    def deselect_all_files(self, tree):
        """모든 파일 선택 해제"""
        for item in tree.get_children():
            values = list(tree.item(item, "values"))
            values[0] = "☐"
            tree.item(item, values=values)
    
    def download_selected_files(self, tree, change_type):
        """선택된 파일들 다운로드"""
        selected_files = []
        for item in tree.get_children():
            values = tree.item(item, "values")
            if values[0] == "☑":  # 선택된 파일
                file_path = values[1]
                selected_files.append(file_path)
        
        if not selected_files:
            messagebox.showwarning("Warning", "No files selected for download.")
            return
        
        # 다운로드 디렉토리 선택
        download_dir = filedialog.askdirectory(title="Select download directory")
        if not download_dir:
            return
        
        # diff 창에서 서버 정보 가져오기
        diff_window = tree.master.master.master  # tree -> frame -> main_frame -> diff_window
        server_config = diff_window.server_config
        manifest = diff_window.manifest
        
        # 다운로드 시작
        self.start_file_download(selected_files, server_config, manifest, download_dir, change_type)
    
    def start_file_download(self, selected_files, server_config, manifest, download_dir, change_type):
        """파일 다운로드 시작"""
        # 다운로드 진행 창 생성
        progress_window = tk.Toplevel(self.root)
        progress_window.title(f"Downloading {change_type} files")
        progress_window.geometry("600x400")
        progress_window.grab_set()  # 모달 창으로 설정
        
        # 메인 프레임
        main_frame = ttk.Frame(progress_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        ttk.Label(main_frame, text=f"Downloading {len(selected_files)} files", font=("Arial", 12, "bold")).pack(pady=10)
        
        # 진행률 표시
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, pady=5)
        
        # 상태 라벨
        status_label = ttk.Label(main_frame, text="Preparing download...", font=("Arial", 10))
        status_label.pack(pady=5)
        
        # 파일 목록 표시
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        file_listbox = tk.Listbox(list_frame, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=file_listbox.yview)
        file_listbox.configure(yscrollcommand=scrollbar.set)
        
        file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 취소 버튼
        cancel_button = ttk.Button(main_frame, text="Cancel", command=progress_window.destroy)
        cancel_button.pack(pady=10)
        
        # 백그라운드에서 다운로드 실행
        download_thread = threading.Thread(target=self.download_files_background, 
                                         args=(selected_files, server_config, manifest, download_dir, 
                                              progress_var, status_label, file_listbox, progress_window))
        download_thread.daemon = True
        download_thread.start()
    
    def download_files_background(self, selected_files, server_config, manifest, download_dir, 
                                progress_var, status_label, file_listbox, progress_window):
        """백그라운드에서 파일 다운로드"""
        try:
            pkg_url = server_config['pkg']
            source = manifest.get("source", "")
            total_files = len(selected_files)
            
            for i, file_path in enumerate(selected_files):
                # 파일 정보 찾기
                file_entry = None
                for entry in manifest.get("file", []):
                    if entry["path"] == file_path:
                        file_entry = entry
                        break
                
                if not file_entry:
                    continue
                
                # 상태 업데이트
                self.root.after(0, lambda f=file_path: status_label.config(text=f"Downloading: {f}"))
                self.root.after(0, lambda f=file_path: file_listbox.insert(tk.END, f"Downloading: {f}"))
                
                # 기존 download_file 함수 사용
                success = download_file(pkg_url, source, file_entry, download_dir)
                
                if success:
                    # 성공 표시
                    self.root.after(0, lambda f=file_path: file_listbox.insert(tk.END, f"✓ Completed: {f}"))
                else:
                    # 실패 표시
                    self.root.after(0, lambda f=file_path: file_listbox.insert(tk.END, f"✗ Failed: {f}"))
                
                # 진행률 업데이트
                progress = (i + 1) / total_files * 100
                self.root.after(0, lambda p=progress: progress_var.set(p))
            
            # 완료 메시지
            self.root.after(0, lambda: status_label.config(text="Download completed!"))
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Downloaded {total_files} files to {download_dir}"))
            
        except Exception as e:
            self.root.after(0, lambda: status_label.config(text=f"Error: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("Error", f"Download failed: {str(e)}"))
        
    def compare_servers(self):
        if len(self.server_data) < 2:
            messagebox.showwarning("Warning", "Need at least 2 servers to compare.")
            return
            
        # 서버 비교 창 생성
        compare_window = tk.Toplevel(self.root)
        compare_window.title("Server Comparison")
        compare_window.geometry("1200x700")
        
        # 메인 프레임
        main_frame = ttk.Frame(compare_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        ttk.Label(main_frame, text="Server Comparison", font=("Arial", 16, "bold")).pack(pady=10)
        
        # 서버 정보 요약
        summary_frame = ttk.LabelFrame(main_frame, text="Server Summary", padding=10)
        summary_frame.pack(fill=tk.X, pady=5)
        
        # 서버별 요약 정보 표시
        summary_text = tk.Text(summary_frame, height=6, wrap=tk.WORD)
        summary_scrollbar = ttk.Scrollbar(summary_frame, orient=tk.VERTICAL, command=summary_text.yview)
        summary_text.configure(yscrollcommand=summary_scrollbar.set)
        
        summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        summary_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 서버 요약 정보 생성
        summary_info = self.generate_server_summary()
        summary_text.insert(tk.END, summary_info)
        summary_text.config(state=tk.DISABLED)
        
        # 파일 비교 프레임
        compare_frame = ttk.LabelFrame(main_frame, text="File Comparison", padding=10)
        compare_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 검색 프레임
        search_frame = ttk.Frame(compare_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.compare_search_var = tk.StringVar()
        compare_search_entry = ttk.Entry(search_frame, textvariable=self.compare_search_var)
        compare_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 키보드 입력 이벤트 바인딩
        compare_search_entry.bind("<KeyRelease>", self.on_compare_search_key)
        
        # 검색 결과 표시 라벨
        self.compare_search_result_label = ttk.Label(search_frame, text="", foreground="gray")
        self.compare_search_result_label.pack(side=tk.RIGHT, padx=5)
        
        # 파일 비교 트리뷰
        columns = ("File", "Size", "Hash", "Status")
        self.compare_tree = ttk.Treeview(compare_frame, columns=columns, show="headings", height=15)
        
        # 컬럼 설정
        self.compare_tree.heading("File", text="File Path")
        self.compare_tree.heading("Size", text="Size")
        self.compare_tree.heading("Hash", text="Hash")
        self.compare_tree.heading("Status", text="Status")
        
        # 컬럼 크기를 내용에 맞게 자동 조정
        self.compare_tree.column("File", width=350, minwidth=250)
        self.compare_tree.column("Size", width=80, minwidth=65)
        self.compare_tree.column("Hash", width=150, minwidth=150)
        self.compare_tree.column("Status", width=100, minwidth=80)
        
        # 스크롤바
        compare_scrollbar = ttk.Scrollbar(compare_frame, orient=tk.VERTICAL, command=self.compare_tree.yview)
        self.compare_tree.configure(yscrollcommand=compare_scrollbar.set)
        
        self.compare_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        compare_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 파일 비교 데이터 로드
        self.load_file_comparison()
        
        # 파일 클릭 이벤트
        self.compare_tree.bind("<Double-1>", self.show_file_details)
        
        # 기준 서버 선택 프레임
        reference_frame = ttk.LabelFrame(main_frame, text="Reference Server", padding=10)
        reference_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(reference_frame, text="Compare against:").pack(side=tk.LEFT, padx=5)
        
        self.reference_var = tk.StringVar()
        self.reference_combo = ttk.Combobox(reference_frame, textvariable=self.reference_var, state="readonly")
        
        # 서버 목록 추가
        server_names = []
        for k, data in self.server_data.items():
            server = data["server"]
            server_names.append(f"{k}. {server['name']}")
        
        self.reference_combo['values'] = server_names
        if server_names:
            self.reference_combo.set(server_names[0])  # 기본값 설정
        
        self.reference_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(reference_frame, text="Apply Reference", command=self.apply_reference).pack(side=tk.LEFT, padx=5)
        
        # 하단 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Refresh Comparison", command=lambda: self.load_file_comparison()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show File Details", command=self.show_file_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=compare_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.reference_server = None  # 기준 서버 저장
        
    def apply_reference(self):
        selected = self.reference_combo.get()
        if not selected:
            return
            
        # 선택된 서버 키 추출
        server_key = selected.split('.')[0]
        self.reference_server = server_key
        
        # 비교 테이블 새로고침
        self.load_file_comparison()
        
    def generate_server_summary(self):
        summary = "Server Comparison Summary:\n\n"
        
        for k, data in self.server_data.items():
            server = data["server"]
            manifest = data["manifest"]
            
            if manifest:
                total_files = len(manifest.get("file", []))
                total_size = sum(int(f.get("size", 0)) for f in manifest.get("file", []))
                total_size_kb = total_size / 1024
                
                summary += f"• {server['name']}: {total_files} files, {total_size_kb:.0f}KB\n"
            else:
                summary += f"• {server['name']}: No data available\n"
                
        return summary
        
    def on_compare_search_key(self, event):
        """파일 비교 검색 키보드 입력 이벤트 핸들러"""
        # 이벤트 위젯에서 직접 값 가져오기
        search_text = event.widget.get()
        
        # StringVar 업데이트
        self.compare_search_var.set(search_text)
        
        # 파일 비교 목록 새로고침
        self.refresh_compare_file_list()
    
    def refresh_compare_file_list(self):
        """파일 비교 목록 새로고침 (검색어 유지)"""
        search_term = self.compare_search_var.get().lower()
        
        # 트리뷰 초기화
        for item in self.compare_tree.get_children():
            self.compare_tree.delete(item)
            
        # 모든 서버의 파일 정보 수집
        all_files = {}
        
        for k, data in self.server_data.items():
            server = data["server"]
            manifest = data["manifest"]
            
            if not manifest:
                continue
                
            for file_entry in manifest.get("file", []):
                file_path = file_entry.get("path", "")
                
                # 검색어가 비어있으면 모든 파일 표시, 아니면 검색어가 포함된 파일만 표시
                if not search_term or search_term in file_path.lower():
                    file_size = int(file_entry.get("size", 0))
                    file_hash = file_entry.get("hash", "N/A")
                    
                    if file_path not in all_files:
                        all_files[file_path] = {}
                        
                    all_files[file_path][server['name']] = {
                        'size': file_size,
                        'hash': file_hash
                    }
        
        # 파일별로 비교 정보 생성
        filtered_count = 0
        total_count = len(all_files)
        
        for file_path, server_data in all_files.items():
            # 기준 서버가 설정된 경우
            if self.reference_server and self.reference_server in self.server_data:
                ref_server_name = self.server_data[self.reference_server]["server"]["name"]
                ref_data = server_data.get(ref_server_name)
                
                if ref_data:
                    ref_size = ref_data['size']
                    ref_hash = ref_data['hash']
                    
                    # 다른 서버들과 비교
                    size_consistent = all(data['size'] == ref_size for data in server_data.values())
                    hash_consistent = all(data['hash'] == ref_hash for data in server_data.values())
                    
                    if size_consistent and hash_consistent:
                        status = f"✓ Same as {ref_server_name}"
                        status_color = "green"
                    else:
                        status = f"✗ Diff from {ref_server_name}"
                        status_color = "red"
                        
                    # 기준 서버의 크기와 해시 사용
                    size_kb = ref_size / 1024
                    display_hash = ref_hash
                else:
                    # 기준 서버에 해당 파일이 없는 경우
                    status = f"✗ Not in {ref_server_name}"
                    status_color = "red"
                    size_kb = 0
                    display_hash = "N/A"
                    
            else:
                # 기존 방식: 모든 서버 간 비교
                sizes = [data['size'] for data in server_data.values()]
                size_consistent = len(set(sizes)) == 1
                
                hashes = [data['hash'] for data in server_data.values()]
                hash_consistent = len(set(hashes)) == 1
                
                if size_consistent and hash_consistent:
                    status = "✓ Consistent"
                    status_color = "green"
                elif size_consistent:
                    status = "⚠ Size OK, Hash Diff"
                    status_color = "orange"
                else:
                    status = "✗ Different"
                    status_color = "red"
                
                # 평균 크기 계산
                avg_size = sum(sizes) / len(sizes)
                size_kb = avg_size / 1024
                
                # 평균 해시 (첫 번째 서버의 해시 사용)
                display_hash = list(server_data.values())[0]['hash']
            
            # 트리뷰에 추가
            item = self.compare_tree.insert("", tk.END, values=(
                file_path,
                f"{size_kb:.0f}KB",
                display_hash,
                status
            ))
            
            filtered_count += 1
        
        # 검색 결과 표시
        if search_term:
            self.compare_search_result_label.config(text=f"{filtered_count}/{total_count} files")
        else:
            self.compare_search_result_label.config(text=f"{total_count} files")
    
    def load_file_comparison(self):
        """파일 비교 데이터 로드"""
        self.refresh_compare_file_list()
            
        # 모든 서버의 파일 정보 수집
        all_files = {}
        
        for k, data in self.server_data.items():
            server = data["server"]
            manifest = data["manifest"]
            
            if not manifest:
                continue
                
            for file_entry in manifest.get("file", []):
                file_path = file_entry.get("path", "")
                file_size = int(file_entry.get("size", 0))
                file_hash = file_entry.get("hash", "N/A")
                
                if file_path not in all_files:
                    all_files[file_path] = {}
                    
                all_files[file_path][server['name']] = {
                    'size': file_size,
                    'hash': file_hash
                }
        
        # 파일별로 비교 정보 생성
        for file_path, server_data in all_files.items():
            if len(server_data) < 2:
                continue  # 최소 2개 서버에 있는 파일만 비교
                
            # 기준 서버가 설정된 경우 기준 서버와 비교
            if self.reference_server and self.reference_server in self.server_data:
                reference_server_name = self.server_data[self.reference_server]["server"]["name"]
                
                if reference_server_name not in server_data:
                    continue  # 기준 서버에 해당 파일이 없으면 스킵
                    
                # 기준 서버의 파일 정보
                ref_size = server_data[reference_server_name]['size']
                ref_hash = server_data[reference_server_name]['hash']
                
                # 다른 서버들과 비교
                different_servers = []
                for server_name, data in server_data.items():
                    if server_name != reference_server_name:
                        if data['size'] != ref_size or data['hash'] != ref_hash:
                            different_servers.append(server_name)
                
                # 상태 결정
                if not different_servers:
                    status = f"✓ Same as {reference_server_name}"
                    status_color = "green"
                else:
                    status = f"✗ Diff from {reference_server_name}"
                    status_color = "red"
                    
                # 기준 서버의 크기와 해시 사용
                size_kb = ref_size / 1024
                display_hash = ref_hash
                
            else:
                # 기존 방식: 모든 서버 간 비교
                sizes = [data['size'] for data in server_data.values()]
                size_consistent = len(set(sizes)) == 1
                
                hashes = [data['hash'] for data in server_data.values()]
                hash_consistent = len(set(hashes)) == 1
                
                if size_consistent and hash_consistent:
                    status = "✓ Consistent"
                    status_color = "green"
                elif size_consistent:
                    status = "⚠ Size OK, Hash Diff"
                    status_color = "orange"
                else:
                    status = "✗ Different"
                    status_color = "red"
                
                # 평균 크기 계산
                avg_size = sum(sizes) / len(sizes)
                size_kb = avg_size / 1024
                
                # 평균 해시 (첫 번째 서버의 해시 사용)
                display_hash = list(server_data.values())[0]['hash']
            
            # 트리뷰에 추가
            item = self.compare_tree.insert("", tk.END, values=(
                file_path,
                f"{size_kb:.0f}KB",
                display_hash,
                status
            ))
            
            # 상태에 따른 색상 설정
            if status_color == "green":
                self.compare_tree.set(item, "Status", status)
            elif status_color == "orange":
                self.compare_tree.set(item, "Status", status)
            else:
                self.compare_tree.set(item, "Status", status)
                
    def show_file_details(self, event=None):
        selection = self.compare_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a file to view details.")
            return
            
        # 선택된 파일 정보 가져오기
        item = self.compare_tree.item(selection[0])
        file_path = item['values'][0]
        
        # 파일 상세 정보 창 생성
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"File Details: {os.path.basename(file_path)}")
        detail_window.geometry("800x700")
        
        # 메인 프레임
        main_frame = ttk.Frame(detail_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        ttk.Label(main_frame, text=f"File Details: {file_path}", font=("Arial", 14, "bold")).pack(pady=10)
        
        # 서버별 파일 정보 테이블
        columns = ("Server", "Size", "Hash", "Status")
        detail_tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=10)
        
        # 컬럼 설정
        detail_tree.heading("Server", text="Server")
        detail_tree.heading("Size", text="Size")
        detail_tree.heading("Hash", text="Hash")
        detail_tree.heading("Status", text="Status")
        
        # 컬럼 크기를 내용에 맞게 자동 조정
        detail_tree.column("Server", width=80, minwidth=80)
        detail_tree.column("Size", width=80, minwidth=65)
        detail_tree.column("Hash", width=150, minwidth=150)
        detail_tree.column("Status", width=100, minwidth=80)
        
        # 스크롤바
        detail_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=detail_tree.yview)
        detail_tree.configure(yscrollcommand=detail_scrollbar.set)
        
        detail_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 파일 정보 수집 및 표시
        file_info = {}
        sizes = []
        hashes = []
        
        for k, data in self.server_data.items():
            server = data["server"]
            manifest = data["manifest"]
            
            if not manifest:
                continue
                
            # 해당 파일 찾기
            for file_entry in manifest.get("file", []):
                if file_entry.get("path", "") == file_path:
                    file_size = int(file_entry.get("size", 0))
                    file_hash = file_entry.get("hash", "N/A")
                    
                    file_info[server['name']] = {
                        'size': file_size,
                        'hash': file_hash
                    }
                    
                    sizes.append(file_size)
                    hashes.append(file_hash)
                    break
        
        # 서버별 정보 표시
        for server_name, info in file_info.items():
            size_kb = info['size'] / 1024
            
            # 상태 결정
            if len(set(sizes)) == 1 and len(set(hashes)) == 1:
                status = "✓ Consistent"
            elif len(set(sizes)) == 1:
                status = "⚠ Hash Diff"
            else:
                status = "✗ Different"
            
            detail_tree.insert("", tk.END, values=(
                server_name,
                f"{size_kb:.0f}KB",
                info['hash'],
                status
            ))
        
        # 통계 정보 프레임
        stats_frame = ttk.LabelFrame(main_frame, text="File Statistics", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 통계 계산
        if sizes:
            min_size = min(sizes)
            max_size = max(sizes)
            avg_size = sum(sizes) / len(sizes)
            
            min_size_kb = min_size / 1024
            max_size_kb = max_size / 1024
            avg_size_kb = avg_size / 1024
            
            size_consistent = len(set(sizes)) == 1
            hash_consistent = len(set(hashes)) == 1
            
            stats_text = f"""
File Statistics:
• Servers with this file: {len(file_info)}
• Size range: {min_size_kb:.0f}KB - {max_size_kb:.0f}KB
• Average size: {avg_size_kb:.0f}KB
• Size consistency: {'✓ All same' if size_consistent else '✗ Different'}
• Hash consistency: {'✓ All same' if hash_consistent else '✗ Different'}
• Total variations: {len(set(sizes))} size(s), {len(set(hashes))} hash(es)
            """
            
            stats_label = ttk.Label(stats_frame, text=stats_text.strip(), font=("Arial", 10), wraplength=500)
            stats_label.pack(anchor=tk.W, fill=tk.X)
        
        # 하단 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Copy Hash", command=lambda: self.copy_to_clipboard(file_info)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=detail_window.destroy).pack(side=tk.RIGHT, padx=5)
        
    def copy_to_clipboard(self, file_info):
        # 해시 정보를 클립보드에 복사
        hash_text = "File Hash Information:\n\n"
        for server_name, info in file_info.items():
            hash_text += f"{server_name}: {info['hash']}\n"
        
        self.root.clipboard_clear()
        self.root.clipboard_append(hash_text)
        messagebox.showinfo("Info", "Hash information copied to clipboard!")
        
    def select_server(self, event=None):
        selection = self.server_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a server.")
            return
            
        server_key = str(selection[0] + 1)  # 1-based index
        if server_key not in self.server_data:
            messagebox.showerror("Error", "Selected server data is not available.")
            return
            
        server_info = self.server_data[server_key]
        server = server_info["server"]
        manifest = server_info["manifest"]
        
        if not manifest:
            messagebox.showerror("Error", "Manifest data is not available for this server.")
            return
            
        # 파일 다운로더 GUI 열기 (서버 목록 창은 유지)
        source = manifest["source"]
        app = FileDownloaderGUI(server, manifest, server["pkg"], source)
        app.run()
        
    def run(self):
        self.root.mainloop()


def main():
    # GUI 모드로 시작
    app = ServerSelectorGUI()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[INFO] Program cancelled by user")
