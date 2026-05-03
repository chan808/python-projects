from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SubmitMode = Literal["preview", "submit"]
FieldAction = Literal["fill", "type", "select_option"]


class ProductInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    brand_name: str
    product_name: str
    product_code: str
    category: str
    price: int = Field(ge=0)
    color: Optional[str] = None
    material: Optional[str] = None
    size: Optional[str] = None
    description: Optional[str] = None
    submit_mode: SubmitMode = "preview"

    @field_validator("brand_name", "product_name", "product_code", "category")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value:
            raise ValueError("Value cannot be empty.")
        return value

    @property
    def price_text(self) -> str:
        return str(self.price)


class RuntimePaths(BaseModel):
    project_root: Path
    settings_dir: Path
    runtime_root: Path
    user_config_path: Path
    register_pic_root: Path
    logs_dir: Path
    screenshots_dir: Path
    output_dir: Path


class BrowserConfig(BaseModel):
    headless: bool = False
    slow_mo_ms: int = Field(default=250, ge=0)
    navigation_timeout_ms: int = Field(default=15000, ge=1000)
    action_timeout_ms: int = Field(default=10000, ge=1000)
    user_data_dir: Path


class SiteConfig(BaseModel):
    register_url: str = ""
    login_check_selector: str = ""
    allow_manual_login: bool = True
    manual_login_timeout_ms: int = Field(default=300000, ge=1000)
    selectors_path: Path


class AppConfig(BaseModel):
    paths: RuntimePaths
    browser: BrowserConfig
    mustit: SiteConfig
    trenbe: SiteConfig
    fillway: SiteConfig
    brand_aliases: Dict[str, str] = Field(default_factory=dict)
    last_ui: Dict[str, Any] = Field(default_factory=dict)


class FieldSelectorConfig(BaseModel):
    selector: str
    action: FieldAction = "fill"
    value_template: Optional[str] = None


class UploadSelectorConfig(BaseModel):
    selector: str


class SiteSelectors(BaseModel):
    fields: Dict[str, FieldSelectorConfig]
    image_upload: UploadSelectorConfig
    submit_button: Optional[UploadSelectorConfig] = None


class UploadResult(BaseModel):
    site: str
    product_code: str
    success: bool
    submit_mode: SubmitMode
    started_at: datetime
    finished_at: datetime
    message: str
    screenshot_path: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
