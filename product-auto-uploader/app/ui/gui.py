from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from app.config import get_app_directories, load_config, load_credentials, load_user_settings, save_credentials, save_user_settings
from app.services.excel_service import brand_name_from_path, load_products_from_excel
from app.services.upload_service import UPLOADER_CLASSES, UploadService
from app.models import ProductInput
from app.utils.logging_utils import setup_logger

SITE_LABELS: Dict[str, str] = {
    "mustit": "머스트잇",
    "trenbe": "트렌비",
    "fillway": "필웨이",
}


class QueueLogHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        self.log_queue.put(("log", self.format(record)))


class ProductAutoUploaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Product Auto Uploader")
        self.root.geometry("980x900")

        self.event_queue: queue.Queue = queue.Queue()
        self.user_settings = load_user_settings()
        self.config = load_config()
        self.logger = setup_logger(self.config.paths.logs_dir)
        self._attach_queue_logger()

        self.is_busy = False
        self._stop_auto = False
        self.products: List[ProductInput] = []
        self.current_index: int = 0
        self.action_buttons: List[ttk.Button] = []

        self._build_ui()
        self._load_values()
        self.root.after(150, self._drain_event_queue)

    # ── UI 구성 ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        note = "비밀번호는 저장하지 않습니다. 최초 1회 브라우저에서 수동 로그인 후 세션이 로컬에 저장됩니다."
        ttk.Label(container, text=note, wraplength=920, justify="left").pack(fill="x", pady=(0, 8))

        self._build_settings_section(container)
        self._build_credentials_section(container)
        self._build_upload_section(container)
        self._build_login_buttons(container)

        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(container, textvariable=self.status_var).pack(fill="x", pady=(4, 2))

        log_frame = ttk.LabelFrame(container, text="실행 로그", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=10, wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _build_settings_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="설정", padding=10)
        frame.pack(fill="x", pady=(0, 8))
        frame.grid_columnconfigure(1, weight=1)

        self.register_pic_root_var = tk.StringVar()
        self._add_row(frame, "이미지 루트 폴더", self.register_pic_root_var, 0, browse_dir=True)

        self.site_url_vars: Dict[str, tk.StringVar] = {}
        self.site_selector_vars: Dict[str, tk.StringVar] = {}
        row = 1
        for site, label in SITE_LABELS.items():
            self.site_url_vars[site] = tk.StringVar()
            self.site_selector_vars[site] = tk.StringVar()
            self._add_row(frame, f"{label} 등록 URL", self.site_url_vars[site], row)
            self._add_row(frame, f"{label} 로그인확인 셀렉터", self.site_selector_vars[site], row + 1)
            row += 2

    def _build_credentials_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="계정 정보 (자동 로그인)", padding=10)
        frame.pack(fill="x", pady=(0, 8))

        self.cred_id_vars: Dict[str, tk.StringVar] = {}
        self.cred_pw_vars: Dict[str, tk.StringVar] = {}

        for col, (site, label) in enumerate(SITE_LABELS.items()):
            site_frame = ttk.Frame(frame)
            site_frame.grid(row=0, column=col, sticky="w", padx=(0, 24))

            ttk.Label(site_frame, text=label, font=("", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

            id_var = tk.StringVar()
            pw_var = tk.StringVar()
            self.cred_id_vars[site] = id_var
            self.cred_pw_vars[site] = pw_var

            ttk.Label(site_frame, text="아이디").grid(row=1, column=0, sticky="w", padx=(0, 6))
            ttk.Entry(site_frame, textvariable=id_var, width=18).grid(row=1, column=1, sticky="w")

            ttk.Label(site_frame, text="비밀번호").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=(4, 0))
            ttk.Entry(site_frame, textvariable=pw_var, width=18, show="*").grid(row=2, column=1, sticky="w", pady=(4, 0))

        note = "credentials.json 에 저장됩니다. 로그인 버튼 없이 업로드 시 자동으로 로그인합니다."
        ttk.Label(frame, text=note, foreground="#888").grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _build_upload_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="업로드", padding=10)
        frame.pack(fill="x", pady=(0, 8))
        frame.grid_columnconfigure(1, weight=1)

        # 엑셀 파일
        self.excel_path_var = tk.StringVar()
        self._add_row(frame, "엑셀 파일", self.excel_path_var, 0, browse_file=True)

        # 브랜드명
        ttk.Label(frame, text="브랜드명").grid(row=1, column=0, sticky="w", pady=4)
        self.brand_label_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.brand_label_var, foreground="#0055cc").grid(
            row=1, column=1, sticky="w", pady=4, padx=(8, 0)
        )

        # 업로드 사이트
        ttk.Label(frame, text="업로드 사이트").grid(row=2, column=0, sticky="w", pady=4)
        site_row = ttk.Frame(frame)
        site_row.grid(row=2, column=1, sticky="w", padx=(8, 0))
        self.site_check_vars: Dict[str, tk.BooleanVar] = {}
        for site, label in SITE_LABELS.items():
            var = tk.BooleanVar(value=True)
            self.site_check_vars[site] = var
            ttk.Checkbutton(site_row, text=label, variable=var).pack(side="left", padx=(0, 16))

        # 구분선
        ttk.Separator(frame, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="we", pady=8)

        # 현재 상품 내비게이션
        nav_frame = ttk.Frame(frame)
        nav_frame.grid(row=4, column=0, columnspan=3, sticky="we")

        self.prev_btn = ttk.Button(nav_frame, text="◀ 이전", width=8, command=self._on_prev)
        self.prev_btn.pack(side="left")

        self.position_var = tk.StringVar(value="0 / 0")
        ttk.Label(nav_frame, textvariable=self.position_var, width=12, anchor="center").pack(side="left", padx=6)

        self.next_btn = ttk.Button(nav_frame, text="다음 ▶", width=8, command=self._on_next)
        self.next_btn.pack(side="left")

        ttk.Label(nav_frame, text="  행 이동:").pack(side="left", padx=(16, 4))
        self.goto_var = tk.StringVar()
        ttk.Entry(nav_frame, textvariable=self.goto_var, width=6).pack(side="left")
        ttk.Button(nav_frame, text="이동", command=self._on_goto).pack(side="left", padx=(4, 0))

        # 현재 상품 정보
        info_frame = ttk.LabelFrame(frame, text="현재 상품", padding=8)
        info_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=(6, 0))
        info_frame.grid_columnconfigure(1, weight=1)
        info_frame.grid_columnconfigure(3, weight=1)

        self._product_vars: Dict[str, tk.StringVar] = {}
        fields = [
            ("상품명", "product_name", 0, 0),
            ("레퍼런스", "product_code", 1, 0),
            ("카테고리", "category", 0, 2),
            ("가격", "price", 1, 2),
            ("색상", "color", 2, 0),
            ("사이즈", "size", 2, 2),
        ]
        for label, key, r, c in fields:
            var = tk.StringVar()
            self._product_vars[key] = var
            ttk.Label(info_frame, text=label, foreground="#555").grid(row=r, column=c, sticky="w", padx=(0 if c == 0 else 16, 4))
            ttk.Label(info_frame, textvariable=var, foreground="#111").grid(row=r, column=c + 1, sticky="w")

        # 구분선
        ttk.Separator(frame, orient="horizontal").grid(row=6, column=0, columnspan=3, sticky="we", pady=8)

        # 업로드 모드 + 실행 버튼
        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.grid(row=7, column=0, columnspan=3, sticky="we")

        ttk.Label(ctrl_frame, text="업로드 모드:").pack(side="left")
        self.auto_mode_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(ctrl_frame, text="수동", variable=self.auto_mode_var, value=False,
                        command=self._on_mode_changed).pack(side="left", padx=(8, 4))
        ttk.Radiobutton(ctrl_frame, text="자동", variable=self.auto_mode_var, value=True,
                        command=self._on_mode_changed).pack(side="left", padx=(0, 24))

        self.upload_btn = ttk.Button(ctrl_frame, text="업로드", width=12, command=self._on_upload_current)
        self.upload_btn.pack(side="left", padx=(0, 6))
        self.action_buttons.append(self.upload_btn)

        self.auto_start_btn = ttk.Button(ctrl_frame, text="▶ 자동 시작", width=12, command=self._on_auto_start)
        self.auto_start_btn.pack(side="left", padx=(0, 6))
        self.auto_start_btn.pack_forget()

        self.auto_stop_btn = ttk.Button(ctrl_frame, text="■ 정지", width=8, command=self._on_auto_stop)
        self.auto_stop_btn.pack(side="left")
        self.auto_stop_btn.pack_forget()

        self.excel_path_var.trace_add("write", self._on_excel_path_changed)

    def _build_login_buttons(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 4))

        self.save_btn = ttk.Button(row, text="설정 저장", command=self._on_save_settings)
        self.save_btn.pack(side="left", padx=(0, 6))

        for site, label in SITE_LABELS.items():
            btn = ttk.Button(row, text=f"{label} 로그인", command=lambda s=site: self._on_prepare_login(s))
            btn.pack(side="left", padx=(0, 6))
            self.action_buttons.append(btn)

        self.open_cfg_btn = ttk.Button(row, text="설정 폴더 열기", command=self._open_settings_dir)
        self.open_cfg_btn.pack(side="left")

    def _add_row(self, parent, label, variable, row, browse_dir=False, browse_file=False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=85).grid(row=row, column=1, sticky="we", pady=3, padx=(8, 0))
        if browse_dir:
            ttk.Button(parent, text="폴더 선택", command=lambda v=variable: self._browse_dir(v)).grid(
                row=row, column=2, padx=(6, 0))
        if browse_file:
            ttk.Button(parent, text="파일 선택", command=lambda v=variable: self._browse_excel(v)).grid(
                row=row, column=2, padx=(6, 0))

    # ── 값 로드/저장 ────────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        self.register_pic_root_var.set(self.user_settings.get("paths", {}).get("register_pic_root", ""))
        for site in SITE_LABELS:
            cfg = self.user_settings.get(site, {})
            self.site_url_vars[site].set(cfg.get("register_url", ""))
            self.site_selector_vars[site].set(cfg.get("login_check_selector", ""))

        creds = load_credentials()
        for site in SITE_LABELS:
            self.cred_id_vars[site].set(creds.get(site, {}).get("id", ""))
            self.cred_pw_vars[site].set(creds.get(site, {}).get("pw", ""))

        ui = self.user_settings.get("ui", {})
        excel_path = ui.get("excel_path", "")
        self.excel_path_var.set(excel_path)
        sites_selected = ui.get("sites_selected", {})
        for site, var in self.site_check_vars.items():
            var.set(sites_selected.get(site, True))

        if excel_path and Path(excel_path).exists():
            self._load_excel(excel_path)

    def _collect_settings_payload(self) -> Dict[str, Any]:
        settings = load_user_settings()
        settings.setdefault("paths", {})
        settings["paths"]["register_pic_root"] = self.register_pic_root_var.get().strip()
        for site in SITE_LABELS:
            settings.setdefault(site, {})
            settings[site]["register_url"] = self.site_url_vars[site].get().strip()
            settings[site]["login_check_selector"] = self.site_selector_vars[site].get().strip()
        settings.setdefault("ui", {})
        settings["ui"]["excel_path"] = self.excel_path_var.get().strip()
        settings["ui"]["sites_selected"] = {s: v.get() for s, v in self.site_check_vars.items()}
        return settings

    def _save_settings(self) -> None:
        settings = self._collect_settings_payload()
        save_user_settings(settings)
        self.user_settings = settings

        creds = {
            site: {"id": self.cred_id_vars[site].get().strip(), "pw": self.cred_pw_vars[site].get()}
            for site in SITE_LABELS
        }
        save_credentials(creds)

        self.config = load_config()

    def _save_last_row(self, index: int) -> None:
        settings = load_user_settings()
        excel_path = self.excel_path_var.get().strip()
        settings.setdefault("ui", {})
        settings["ui"]["last_row"] = {excel_path: index}
        save_user_settings(settings)
        self.user_settings = settings

    def _get_saved_last_row(self, excel_path: str) -> int:
        last_row_map = self.user_settings.get("ui", {}).get("last_row", {})
        return last_row_map.get(excel_path, -1)

    # ── 상품 로드 / 내비게이션 ─────────────────────────────────────────────────

    def _load_excel(self, path: str) -> None:
        try:
            self.products = load_products_from_excel(Path(path))
        except Exception as exc:
            self.products = []
            self.logger.warning("엑셀 로드 실패: %s", exc)

        last = self._get_saved_last_row(path)
        start = min(last + 1, len(self.products) - 1) if last >= 0 and self.products else 0
        self.current_index = start
        self._refresh_product_display()

    def _refresh_product_display(self) -> None:
        total = len(self.products)
        if total == 0:
            self.position_var.set("0 / 0")
            for var in self._product_vars.values():
                var.set("")
            return

        idx = self.current_index
        self.position_var.set(f"{idx + 1} / {total}")
        p = self.products[idx]
        self._product_vars["product_name"].set(p.product_name)
        self._product_vars["product_code"].set(p.product_code)
        self._product_vars["category"].set(p.category)
        self._product_vars["price"].set(f"{p.price:,}원")
        self._product_vars["color"].set(p.color or "-")
        self._product_vars["size"].set(str(p.size) if p.size else "-")

    def _on_prev(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._refresh_product_display()

    def _on_next(self) -> None:
        if self.current_index < len(self.products) - 1:
            self.current_index += 1
            self._refresh_product_display()

    def _on_goto(self) -> None:
        try:
            row = int(self.goto_var.get().strip())
            if 1 <= row <= len(self.products):
                self.current_index = row - 1
                self._refresh_product_display()
            else:
                messagebox.showwarning("범위 초과", f"1 ~ {len(self.products)} 사이의 번호를 입력하세요.")
        except ValueError:
            messagebox.showwarning("입력 오류", "숫자를 입력하세요.")

    def _on_mode_changed(self) -> None:
        if self.auto_mode_var.get():
            self.upload_btn.pack_forget()
            self.auto_start_btn.pack(side="left", padx=(0, 6))
        else:
            self.auto_start_btn.pack_forget()
            self.auto_stop_btn.pack_forget()
            self.upload_btn.pack(side="left", padx=(0, 6))

    # ── 이벤트 핸들러 ──────────────────────────────────────────────────────────

    def _on_excel_path_changed(self, *_) -> None:
        path_str = self.excel_path_var.get().strip()
        self.brand_label_var.set(brand_name_from_path(Path(path_str)) if path_str else "")
        if path_str and Path(path_str).exists():
            self._load_excel(path_str)

    def _on_save_settings(self) -> None:
        try:
            self._save_settings()
        except Exception as exc:
            messagebox.showerror("설정 저장 실패", str(exc))
            return
        messagebox.showinfo("설정 저장", "설정을 저장했습니다.")

    def _on_prepare_login(self, site: str) -> None:
        if self.is_busy:
            return
        self._run_background_task(lambda s=site: self._prepare_login_worker(s))

    def _on_upload_current(self) -> None:
        if self.is_busy or not self.products:
            return
        self._run_background_task(lambda: self._upload_single_worker(self.current_index, auto=False))

    def _on_auto_start(self) -> None:
        if self.is_busy or not self.products:
            return
        self._stop_auto = False
        self.auto_start_btn.pack_forget()
        self.auto_stop_btn.pack(side="left")
        self._run_background_task(self._auto_upload_worker)

    def _on_auto_stop(self) -> None:
        self._stop_auto = True
        self.status_var.set("정지 요청됨...")

    # ── 워커 ───────────────────────────────────────────────────────────────────

    def _prepare_login_worker(self, site: str) -> str:
        self._save_settings()
        uploader = UPLOADER_CLASSES[site](self.config, self.logger)
        message = uploader.prepare_login_session()
        return f"[{SITE_LABELS[site]}] {message}"

    def _upload_single_worker(self, index: int, auto: bool = False) -> str:
        self._save_settings()
        excel_path = Path(self.excel_path_var.get().strip())
        if not excel_path.exists():
            raise FileNotFoundError(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")

        selected_sites = [s for s, v in self.site_check_vars.items() if v.get()]
        if not selected_sites:
            raise ValueError("업로드할 사이트를 하나 이상 선택하세요.")

        product = self.products[index]
        service = UploadService(self.config, self.logger)
        results = service.run_batch([product], selected_sites, "submit")

        success = all(r.success for r in results)
        if success:
            self._save_last_row(index)

        label = f"[{index + 1}/{len(self.products)}] {product.product_code}"
        if success:
            return f"{label} 업로드 성공"
        else:
            failed_msgs = "; ".join(r.message for r in results if not r.success)
            raise RuntimeError(f"{label} 업로드 실패: {failed_msgs}")

    def _auto_upload_worker(self) -> str:
        success_count = 0
        fail_count = 0
        total = len(self.products)

        while self.current_index < total and not self._stop_auto:
            idx = self.current_index
            self.event_queue.put(("set_index", idx))
            msg = f"[{idx + 1}/{total}] {self.products[idx].product_code} 업로드 중..."
            self.event_queue.put(("progress", msg))

            try:
                self._upload_single_worker(idx, auto=True)
                success_count += 1
            except Exception as exc:
                fail_count += 1
                self.logger.error("자동 업로드 실패 (행 %d): %s", idx + 1, exc)

            self.current_index += 1

        stopped = self._stop_auto and self.current_index < total
        status = "정지됨" if stopped else "완료"
        return f"자동 업로드 {status}: 성공 {success_count}건 / 실패 {fail_count}건"

    # ── 스레딩 ─────────────────────────────────────────────────────────────────

    def _run_background_task(self, worker: Any) -> None:
        self.is_busy = True
        self._set_buttons_state("disabled")
        self.status_var.set("작업 실행 중...")
        threading.Thread(target=self._worker_wrapper, args=(worker,), daemon=True).start()

    def _worker_wrapper(self, worker: Any) -> None:
        try:
            message = worker()
            self.event_queue.put(("success", message))
        except Exception as exc:
            self.logger.exception("작업 실행 실패")
            self.event_queue.put(("error", str(exc)))
        finally:
            self.event_queue.put(("done", ""))

    def _drain_event_queue(self) -> None:
        while True:
            try:
                event_type, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break
            if event_type == "log":
                self._append_log(payload)
            elif event_type == "progress":
                self.status_var.set(payload)
                self._append_log(payload)
            elif event_type == "set_index":
                self.current_index = payload
                self._refresh_product_display()
            elif event_type == "success":
                self.status_var.set("완료")
                if not self.auto_mode_var.get():
                    # 수동 모드: 성공 후 자동으로 다음 상품으로 이동
                    if self.current_index < len(self.products) - 1:
                        self.current_index += 1
                        self._refresh_product_display()
                messagebox.showinfo("완료", payload)
            elif event_type == "error":
                self.status_var.set("실패")
                messagebox.showerror("오류", payload)
            elif event_type == "done":
                self.is_busy = False
                self._stop_auto = False
                self._set_buttons_state("normal")
                if self.auto_mode_var.get():
                    self.auto_stop_btn.pack_forget()
                    self.auto_start_btn.pack(side="left", padx=(0, 6))
        self.root.after(150, self._drain_event_queue)

    # ── 유틸리티 ───────────────────────────────────────────────────────────────

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_buttons_state(self, state: str) -> None:
        self.save_btn.configure(state=state)
        self.open_cfg_btn.configure(state=state)
        self.prev_btn.configure(state=state)
        self.next_btn.configure(state=state)
        for btn in self.action_buttons:
            btn.configure(state=state)

    def _attach_queue_logger(self) -> None:
        if any(isinstance(h, QueueLogHandler) for h in self.logger.handlers):
            return
        handler = QueueLogHandler(self.event_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self.logger.addHandler(handler)

    def _browse_dir(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(initialdir=variable.get() or os.path.expanduser("~"))
        if selected:
            variable.set(selected)

    def _browse_excel(self, variable: tk.StringVar) -> None:
        initial_dir = str(Path(variable.get()).parent) if variable.get() else os.path.expanduser("~")
        selected = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=[("Excel 파일", "*.xlsx *.xls"), ("모든 파일", "*.*")],
        )
        if selected:
            variable.set(selected)

    def _open_settings_dir(self) -> None:
        settings_dir, _, _ = get_app_directories()
        settings_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(settings_dir))


def main() -> int:
    root = tk.Tk()
    ProductAutoUploaderApp(root)
    root.mainloop()
    return 0
