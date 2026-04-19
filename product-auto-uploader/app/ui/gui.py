from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict

from pydantic import ValidationError

from app.config import get_app_directories, load_config, load_user_settings, save_last_product, save_user_settings
from app.models import ProductInput
from app.services.upload_service import UploadService
from app.uploaders.mustit import MustitUploader
from app.utils.logging_utils import setup_logger


class QueueLogHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        self.log_queue.put(("log", self.format(record)))


class ProductAutoUploaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Product Auto Uploader")
        self.root.geometry("920x760")

        self.event_queue = queue.Queue()
        self.user_settings = load_user_settings()
        self.config = load_config()
        self.logger = setup_logger(self.config.paths.logs_dir)
        self._attach_queue_logger()
        self.is_busy = False

        self._build_ui()
        self._load_values()
        self.root.after(150, self._drain_event_queue)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        note = (
            "비밀번호는 JSON에 저장하지 않습니다. 사용자별 브라우저 세션을 로컬에 저장해서 "
            "반복 로그인을 줄이는 방식입니다."
        )
        ttk.Label(container, text=note, wraplength=860, justify="left").pack(fill="x", pady=(0, 12))

        settings_frame = ttk.LabelFrame(container, text="설정", padding=12)
        settings_frame.pack(fill="x", pady=(0, 12))

        self.register_pic_root_var = tk.StringVar()
        self.register_url_var = tk.StringVar()
        self.login_check_selector_var = tk.StringVar()

        self._add_entry(settings_frame, "이미지 루트 폴더", self.register_pic_root_var, 0, width=70)
        ttk.Button(settings_frame, text="폴더 선택", command=self._browse_register_pic_root).grid(
            row=0, column=2, padx=(8, 0), pady=4, sticky="w"
        )
        self._add_entry(settings_frame, "머스트잇 등록 URL", self.register_url_var, 1, width=80)
        self._add_entry(settings_frame, "로그인 확인 셀렉터", self.login_check_selector_var, 2, width=80)

        product_frame = ttk.LabelFrame(container, text="상품 입력", padding=12)
        product_frame.pack(fill="x", pady=(0, 12))

        self.category_var = tk.StringVar()
        self.brand_name_var = tk.StringVar()
        self.product_code_var = tk.StringVar()
        self.product_name_var = tk.StringVar()
        self.price_var = tk.StringVar()

        self._add_entry(product_frame, "카테고리", self.category_var, 0, width=40)
        self._add_entry(product_frame, "브랜드명", self.brand_name_var, 1, width=40)
        self._add_entry(product_frame, "상품번호", self.product_code_var, 2, width=40)
        self._add_entry(product_frame, "제품명", self.product_name_var, 3, width=60)
        self._add_entry(product_frame, "가격", self.price_var, 4, width=20)

        button_frame = ttk.Frame(container)
        button_frame.pack(fill="x", pady=(0, 12))

        self.save_button = ttk.Button(button_frame, text="설정 저장", command=self._on_save_settings)
        self.save_button.pack(side="left", padx=(0, 8))

        self.prepare_login_button = ttk.Button(
            button_frame, text="로그인 세션 준비", command=self._on_prepare_login
        )
        self.prepare_login_button.pack(side="left", padx=(0, 8))

        self.preview_button = ttk.Button(button_frame, text="미리보기 실행", command=self._on_preview)
        self.preview_button.pack(side="left", padx=(0, 8))

        self.submit_button = ttk.Button(button_frame, text="자동 제출 실행", command=self._on_submit)
        self.submit_button.pack(side="left", padx=(0, 8))

        self.open_config_button = ttk.Button(button_frame, text="설정 폴더 열기", command=self._open_settings_dir)
        self.open_config_button.pack(side="left")

        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(container, textvariable=self.status_var).pack(fill="x", pady=(0, 8))

        log_frame = ttk.LabelFrame(container, text="실행 로그", padding=12)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=20, wrap="word")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _add_entry(self, parent, label: str, variable: tk.StringVar, row: int, width: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=1, sticky="we", pady=4)
        parent.grid_columnconfigure(1, weight=1)

    def _load_values(self) -> None:
        self.register_pic_root_var.set(self.user_settings.get("paths", {}).get("register_pic_root", ""))
        self.register_url_var.set(self.user_settings.get("mustit", {}).get("register_url", ""))
        self.login_check_selector_var.set(self.user_settings.get("mustit", {}).get("login_check_selector", ""))

        last_product = self.user_settings.get("ui", {}).get("last_product", {})
        self.category_var.set(last_product.get("category", ""))
        self.brand_name_var.set(last_product.get("brand_name", ""))
        self.product_code_var.set(last_product.get("product_code", ""))
        self.product_name_var.set(last_product.get("product_name", ""))
        self.price_var.set(last_product.get("price", ""))

    def _collect_settings_payload(self) -> Dict[str, Any]:
        settings = load_user_settings()
        settings.setdefault("paths", {})
        settings.setdefault("mustit", {})
        settings.setdefault("ui", {})

        settings["paths"]["register_pic_root"] = self.register_pic_root_var.get().strip()
        settings["mustit"]["register_url"] = self.register_url_var.get().strip()
        settings["mustit"]["login_check_selector"] = self.login_check_selector_var.get().strip()
        settings["ui"]["last_product"] = self._collect_last_product_payload()
        return settings

    def _collect_last_product_payload(self) -> Dict[str, str]:
        return {
            "category": self.category_var.get().strip(),
            "brand_name": self.brand_name_var.get().strip(),
            "product_code": self.product_code_var.get().strip(),
            "product_name": self.product_name_var.get().strip(),
            "price": self.price_var.get().strip(),
            "submit_mode": "preview",
        }

    def _build_product_input(self, submit_mode: str) -> ProductInput:
        return ProductInput(
            category=self.category_var.get().strip(),
            brand_name=self.brand_name_var.get().strip(),
            product_code=self.product_code_var.get().strip(),
            product_name=self.product_name_var.get().strip(),
            price=int(self.price_var.get().strip()),
            submit_mode=submit_mode,
        )

    def _on_save_settings(self) -> None:
        try:
            self._save_settings()
        except Exception as exc:
            messagebox.showerror("설정 저장 실패", str(exc))
            return
        messagebox.showinfo("설정 저장", "사용자 설정을 저장했습니다.")

    def _on_prepare_login(self) -> None:
        if self.is_busy:
            return
        self._run_background_task(self._prepare_login_worker)

    def _on_preview(self) -> None:
        if self.is_busy:
            return
        self._run_background_task(lambda: self._upload_worker("preview"))

    def _on_submit(self) -> None:
        if self.is_busy:
            return
        confirmed = messagebox.askyesno("자동 제출 확인", "자동 제출을 실행합니다. 계속하시겠습니까?")
        if not confirmed:
            return
        self._run_background_task(lambda: self._upload_worker("submit"))

    def _save_settings(self) -> None:
        settings = self._collect_settings_payload()
        save_user_settings(settings)
        self.user_settings = settings
        self.config = load_config()

    def _prepare_login_worker(self) -> str:
        self._save_settings()
        uploader = MustitUploader(self.config, self.logger)
        return uploader.prepare_login_session()

    def _upload_worker(self, submit_mode: str) -> str:
        self._save_settings()
        product = self._build_product_input(submit_mode)
        save_last_product(
            {
                "category": product.category,
                "brand_name": product.brand_name,
                "product_code": product.product_code,
                "product_name": product.product_name,
                "price": str(product.price),
                "submit_mode": product.submit_mode,
            }
        )
        self.user_settings = load_user_settings()
        self.config = load_config()

        service = UploadService(self.config, self.logger)
        result, result_path = service.run(product)
        summary = "성공" if result.success else "실패"
        message = "%s\n메시지: %s\n결과 파일: %s" % (summary, result.message, result_path)
        if result.screenshot_path:
            message += "\n스크린샷: %s" % result.screenshot_path
        return message

    def _run_background_task(self, worker) -> None:
        self.is_busy = True
        self._set_buttons_state("disabled")
        self.status_var.set("작업 실행 중")
        thread = threading.Thread(target=self._worker_wrapper, args=(worker,), daemon=True)
        thread.start()

    def _worker_wrapper(self, worker) -> None:
        try:
            message = worker()
            self.event_queue.put(("success", message))
        except ValidationError as exc:
            self.logger.error("입력값 검증 실패: %s", exc)
            self.event_queue.put(("error", str(exc)))
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

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_buttons_state(self, state: str) -> None:
        self.save_button.configure(state=state)
        self.prepare_login_button.configure(state=state)
        self.preview_button.configure(state=state)
        self.submit_button.configure(state=state)
        self.open_config_button.configure(state=state)

    def _attach_queue_logger(self) -> None:
        if any(isinstance(handler, QueueLogHandler) for handler in self.logger.handlers):
            return
        handler = QueueLogHandler(self.event_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self.logger.addHandler(handler)

    def _browse_register_pic_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.register_pic_root_var.get() or os.path.expanduser("~"))
        if selected:
            self.register_pic_root_var.set(selected)

    def _open_settings_dir(self) -> None:
        settings_dir, _, _ = get_app_directories()
        settings_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(settings_dir))


def main() -> int:
    root = tk.Tk()
    ProductAutoUploaderApp(root)
    root.mainloop()
    return 0
