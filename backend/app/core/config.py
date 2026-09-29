"""全局配置。

所有可变的东西（密钥、路径、有效期）都从这里取，业务代码里不许写死。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（本文件位于 backend/app/core/config.py）
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Freedom Design 个人工作台"

    # ---- 认证 ----
    secret_key: str = "dev-only-please-change-me"
    access_token_expire_minutes: int = 60 * 24 * 30  # 30 天

    # 本地开发是 http，Cookie 不能带 secure 标记，否则浏览器不会回传。
    # **部署到 HTTPS 之后必须改成 true**，否则登录凭证会在明文连接上传输。
    cookie_secure: bool = False

    # ---- 数据（均为相对 backend/ 的路径）----
    database_file: str = "data/freedom_design.db"
    upload_dir: str = "uploads"

    @property
    def database_path(self) -> Path:
        return BASE_DIR / self.database_file

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def upload_path(self) -> Path:
        return BASE_DIR / self.upload_dir

    def ensure_directories(self) -> None:
        """把数据目录建出来。

        这些目录在 .gitignore 里，所以全新克隆下来的仓库里并不存在，需要启动时创建。
        """
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_path.mkdir(parents=True, exist_ok=True)


settings = Settings()
