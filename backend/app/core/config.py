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

    # ---- AI 模块（第三期 F11~F13）----
    #
    # 这里全部给默认值，所以 .env 里不写这几项也能启动 ——
    # 没配 key 时 AI 模块会明确报「未配置」，其余模块完全不受影响。
    #
    # ★ 模型名和 base_url 刻意做成配置而不是常量：「百炼会定期下线旧模型」
    #   这件事是必然发生的，写死在代码里意味着每次都要改代码重新发版。
    dashscope_api_key: str = ""
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ★ 这两个必须配套。换 embedding 模型却不换维度，旧向量和新向量就不在
    #   同一个向量空间里 —— 检索会返回莫名其妙的内容，而且一路不报错。
    ai_embedding_model: str = "text-embedding-v4"
    ai_embedding_dim: int = 1024

    ai_chat_model: str = "qwen3.7-flash"
    # 思考模式。实测同一个 RAG 问题：开 = 9.6 秒 / 662 思考 token，关 = 2.4 秒 / 0。
    ai_chat_thinking: bool = False

    ai_retrieval_top_k: int = 5
    # ★ 2026-09-30 用 63 篇真实数据实测：正确答案 top-1 在 0.626~0.817，
    #   无关分块最高 0.493，所以取 0.55。这个数字换 embedding 模型后要重测。
    ai_retrieval_min_score: float = 0.55

    ai_chunk_size: int = 500
    ai_chunk_overlap: int = 100

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
