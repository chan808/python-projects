from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List

from app.config import get_app_directories, load_config, load_user_settings, save_user_settings
from app.services.excel_service import brand_name_from_path, load_products_from_excel
from app.services.upload_service import UPLOADER_CLASSES, UploadService
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
        self.root.geometry("980x880")

        self.event_queue: queue.Queue = queue.Queue()
        self.user_settings = load_user_settings()
        self.config = load_config()
        self.logger = setup_logger(self.config.paths.logs_dir)
        self._attach_queue_logger()
        self.is_busy = False
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
        self._build_upload_section(container)
        self._build_buttons(container)

        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(container, textvariable=self.status_var).pack(fill="x", pady=(4, 4))

        log_frame = ttk.LabelFrame(container, text="실행 로그", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=12, wrap="word")
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

    def _build_upload_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="업로드", padding=10)
        frame.pack(fill="x", pady=(0, 8))
        frame.grid_columnconfigure(1, weight=1)

        self.excel_path_var = tk.StringVar()
        self._add_row(frame, "엑셀 파일", self.excel_path_var, 0, browse_file=True)

        ttk.Label(frame, text="브랜드명").grid(row=1, column=0, sticky="w", pady=4)
        self.brand_label_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.brand_label_var, foreground="#0055cc").grid(
            row=1, column=1, sticky="w", pady=4, padx=(8, 0)
        )

        ttk.Label(frame, text="업로드 사이트").grid(row=2, column=0, sticky="w", pady=4)
        site_row = ttk.Frame(frame)
        site_row.grid(row=2, column=1, sticky="w", padx=(8, 0))
        self.site_check_vars: Dict[str, tk.BooleanVar] = {}
        for site, label in SITE_LABELS.items():
            var = tk.BooleanVar(value=True)
            self.site_check_vars[site] = var
            ttk.Checkbutton(site_row, text=label, variable=var).pack(side="left", padx=(0, 16))

        self.excel_path_var.trace_add("write", self._on_excel_path_changed)

    def _build_buttons(self, parent: ttk.Frame) -> None:
        row1 = ttk.Frame(parent)
        row1.pack(fill="x", pady=(0, 4))

        self.save_btn = ttk.Button(row1, text="설정 저장", command=self._on_save_settings)
        self.save_btn.pack(side="left", padx=(0, 6))

        for site, label in SITE_LABELS.items():
            btn = ttk.Button(row1, text=f"{label} 로그인", command=lambda s=site: self._on_prepare_login(s))
            btn.pack(side="left", padx=(0, 6))
            self.action_buttons.append(btn)

        self.open_cfg_btn = ttk.Button(row1, text="설정 폴더 열기", command=self._open_settings_dir)
        self.open_cfg_btn.pack(side="left")

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", pady=(0, 4))

        preview_btn = ttk.Button(row2, text="미리보기 (첫 번째 상품)", command=self._on_preview)
        preview_btn.pack(side="left", padx=(0, 6))
        self.action_buttons.append(preview_btn)

        submit_btn = ttk.Button(row2, text="전체 자동 제출", command=self._on_submit)
        submit_btn.pack(side="left")
        self.action_buttons.append(submit_btn)

    def _add_row(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        browse_dir: bool = False,
        browse_file: bool = False,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=85).grid(row=row, column=1, sticky="we", pady=3, padx=(8, 0))
        if browse_dir:
            ttk.Button(parent, text="폴더 선택", command=lambda v=variable: self._browse_dir(v)).grid(
                row=row, column=2, padx=(6, 0)
            )
        if browse_file:
            ttk.Button(parent, text="파일 선택", command=lambda v=variable: self._browse_excel(v)).grid(
                row=row, column=2, padx=(6, 0)
            )

    # ── 값 로드/저장 ────────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        self.register_pic_root_var.set(self.user_settings.get("paths", {}).get("register_pic_root", ""))
        for site in SITE_LABELS:
            cfg = self.user_settings.get(site, {})
            self.site_url_vars[site].set(cfg.get("register_url", ""))
            self.site_selector_vars[site].set(cfg.get("login_check_selector", ""))

        ui = self.user_settings.get("ui", {})
        self.excel_path_var.set(ui.get("excel_path", ""))
        sites_selected = ui.get("sites_selected", {})
        for site, var in self.site_check_vars.items():
            var.set(sites_selected.get(site, True))

    def _collect_settings_payload(self) -> Dict[str, Any]:
        settings = load_user_settings()
        settings.setdefault("paths", {})
        settings["paths"]["register_pic_root"] = self.register_pic_root_var.get().strip()
        for site in SITE_LABELS:
            settings.setdefault(site, {})
            settings[site]["register_url"] = self.site_url_vars[site].get().strip()
            settings[site]["login_check_selector"] = self.site_selector_vars[site].get().strip()
        settings["ui"] = {
            "excel_path": self.excel_path_var.get().strip(),
            "sites_selected": {site: var.get() for site, var in self.site_check_vars.items()},
        }
        return settings

    def _save_settings(self) -> None:
        settings = self._collect_settings_payload()
        save_user_settings(settings)
        self.user_settings = settings
        self.config = load_config()

    # ── 이벤트 핸들러 ──────────────────────────────────────────────────────────

    def _on_excel_path_changed(self, *_) -> None:
        path_str = self.excel_path_var.get().strip()
        self.brand_label_var.set(brand_name_from_path(Path(path_str)) if path_str else "")

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

    def _on_preview(self) -> None:
        if self.is_busy:
            return
        self._run_background_task(lambda: self._upload_worker("preview"))

    def _on_submit(self) -> None:
        if self.is_busy:
            return
        if not messagebox.askyesno("전체 자동 제출 확인", "전체 상품을 자동 제출합니다. 계속하시겠습니까?"):
            return
        self._run_background_task(lambda: self._upload_worker("submit"))

    # ── 워커 ───────────────────────────────────────────────────────────────────

    def _prepare_login_worker(self, site: str) -> str:
        self._save_settings()
        uploader = UPLOADER_CLASSES[site](self.config, self.logger)
        message = uploader.prepare_login_session()
        return f"[{SITE_LABELS[site]}] {message}"

    def _upload_worker(self, submit_mode: str) -> str:
        self._save_settings()
        excel_path = Path(self.excel_path_var.get().strip())
        if not excel_path.exists():
            raise FileNotFoundError(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")

        selected_sites = [site for site, var in self.site_check_vars.items() if var.get()]
        if not selected_sites:
            raise ValueError("업로드할 사이트를 하나 이상 선택하세요.")

        products = load_products_from_excel(excel_path)
        if not products:
            raise ValueError("엑셀에서 유효한 상품을 찾지 못했습니다.")

        if submit_mode == "preview":
            products = products[:1]

        service = UploadService(self.config, self.logger)

        def on_progress(done: int, total: int, code: str, site: str) -> None:
            msg = f"[{done + 1}/{total}] {code} → {SITE_LABELS.get(site, site)}"
            self.event_queue.put(("progress", msg))

        results = service.run_batch(products, selected_sites, submit_mode, on_progress=on_progress)

        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        summary = f"완료: 성공 {success_count}건 / 실패 {fail_count}건"
        if fail_count:
            failed_codes = sorted({r.product_code for r in results if not r.success})[:5]
            summary += f"\n실패 상품: {', '.join(failed_codes)}"
            if len({r.product_code for r in results if not r.success}) > 5:
                summary += " 외..."
        return summary

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
            elif event_type == "success":
                self.status_var.set("완료")
                messagebox.showinfo("작업 완료", payload)
            elif event_type == "error":
                self.status_var.set("실패")
                messagebox.showerror("작업 실패", payload)
            elif event_type == "done":
                self.is_busy = False
                self._set_buttons_state("normal")
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
