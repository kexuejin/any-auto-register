"""
注册流程引擎
从 main.py 中提取并重构的注册流程
"""

from __future__ import annotations

import re
import json
import time
import logging
import random
import secrets
import string
from typing import Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from curl_cffi import requests as cffi_requests

from .oauth import OAuthManager, OAuthStart
from .http_client import OpenAIHTTPClient, HTTPClientError
from .sentinel_pow import build_sentinel_pow_token, SentinelPOWError
# from ..services import EmailServiceFactory, BaseEmailService, EmailServiceType  # removed: external dep
# from ..database import crud  # removed: external dep
# from ..database.session import get_db  # removed: external dep
from .constants import (
    OPENAI_API_ENDPOINTS,
    OPENAI_PAGE_TYPES,
    OTP_RESEND_SCHEDULE,
    generate_random_user_info,
    OTP_CODE_PATTERN,
    DEFAULT_PASSWORD_LENGTH,
    PASSWORD_CHARSET,
    AccountStatus,
    TaskStatus,
)
# from ..config.settings import get_settings  # removed: external dep


logger = logging.getLogger(__name__)

MAX_OAUTH_CHALLENGE_RETRIES = 4


def _should_resend_otp(elapsed: float, last_resend: float, resend_count: int) -> bool:
    if elapsed <= 0:
        return False
    interval = OTP_RESEND_SCHEDULE[min(max(0, resend_count), len(OTP_RESEND_SCHEDULE) - 1)]
    return elapsed >= interval and (elapsed - last_resend) >= interval


@dataclass
class RegistrationResult:
    """注册结果"""
    success: bool
    email: str = ""
    password: str = ""  # 注册密码
    account_id: str = ""
    workspace_id: str = ""
    type: str = "codex"
    name: str = ""
    access_token: str = ""
    refresh_token: str = ""
    id_token: str = ""
    expires_at: str = ""
    registered_at: str = ""
    mode: str = "register"
    team_upgrade: dict = None
    token_health: dict = None
    session_token: str = ""  # 会话令牌
    error_message: str = ""
    logs: list = None
    metadata: dict = None
    source: str = "register"  # 'register' 或 'login'，区分账号来源

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "email": self.email,
            "password": self.password,
            "account_id": self.account_id,
            "workspace_id": self.workspace_id,
            "type": self.type,
            "name": self.name,
            "access_token": self.access_token[:20] + "..." if self.access_token else "",
            "refresh_token": self.refresh_token[:20] + "..." if self.refresh_token else "",
            "id_token": self.id_token[:20] + "..." if self.id_token else "",
            "expires_at": self.expires_at,
            "registered_at": self.registered_at,
            "mode": self.mode,
            "team_upgrade": self.team_upgrade or {},
            "token_health": self.token_health or {},
            "session_token": self.session_token[:20] + "..." if self.session_token else "",
            "error_message": self.error_message,
            "logs": self.logs or [],
            "metadata": self.metadata or {},
            "source": self.source,
        }


@dataclass
class SignupFormResult:
    """提交注册表单的结果"""
    success: bool
    page_type: str = ""  # 响应中的 page.type 字段
    is_existing_account: bool = False  # 是否为已注册账号
    response_data: Dict[str, Any] = None  # 完整的响应数据
    error_message: str = ""


class RegistrationEngine:
    """
    注册引擎
    负责协调邮箱服务、OAuth 流程和 OpenAI API 调用
    """

    def __init__(
        self,
        email_service: BaseEmailService,
        proxy_url: Optional[str] = None,
        callback_logger: Optional[Callable[[str], None]] = None,
        task_uuid: Optional[str] = None
    ):
        """
        初始化注册引擎

        Args:
            email_service: 邮箱服务实例
            proxy_url: 代理 URL
            callback_logger: 日志回调函数
            task_uuid: 任务 UUID（用于数据库记录）
        """
        self.email_service = email_service
        self.proxy_url = proxy_url
        self.callback_logger = callback_logger or (lambda msg: logger.info(msg))
        self.task_uuid = task_uuid

        # 创建 HTTP 客户端
        self.http_client = OpenAIHTTPClient(proxy_url=proxy_url)

        # 创建 OAuth 管理器
        from .constants import OAUTH_CLIENT_ID, OAUTH_AUTH_URL, OAUTH_TOKEN_URL, OAUTH_REDIRECT_URI, OAUTH_SCOPE
        self.oauth_manager = OAuthManager(
            client_id=OAUTH_CLIENT_ID,
            auth_url=OAUTH_AUTH_URL,
            token_url=OAUTH_TOKEN_URL,
            redirect_uri=OAUTH_REDIRECT_URI,
            scope=OAUTH_SCOPE,
            proxy_url=proxy_url  # 传递代理配置
        )

        # 状态变量
        self.email: Optional[str] = None
        self.password: Optional[str] = None  # 注册密码
        self.email_info: Optional[Dict[str, Any]] = None
        self.oauth_start: Optional[OAuthStart] = None
        self.session: Optional[cffi_requests.Session] = None
        self.session_token: Optional[str] = None  # 会话令牌
        self.logs: list = []
        self._otp_sent_at: Optional[float] = None  # OTP 发送时间戳
        self._is_existing_account: bool = False  # 是否为已注册账号（用于自动登录）
        self._last_sentinel_did: str = ""
        self._last_sentinel_token: str = ""
        self._last_sentinel_pow: str = ""
        self._last_sentinel_header: str = ""
        self._create_account_continue_url: Optional[str] = None
        self._used_otp_codes: set[str] = set()
        self._otp_send_url: Optional[str] = None
        self._otp_send_method: Optional[str] = None

    def _log(self, message: str, level: str = "info"):
        """记录日志"""
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"

        # 添加到日志列表
        self.logs.append(log_message)

        # 调用回调函数
        if self.callback_logger:
            self.callback_logger(message)

        # 记录到数据库（如果有关联任务）
        if self.task_uuid:
            try:
                with get_db() as db:
                    crud.append_task_log(db, self.task_uuid, message)
            except Exception as e:
                logger.warning(f"记录任务日志失败: {e}")

        # 根据级别记录到日志系统
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def _generate_password(self, length: int = DEFAULT_PASSWORD_LENGTH) -> str:
        """生成随机密码"""
        return ''.join(secrets.choice(PASSWORD_CHARSET) for _ in range(length))

    def _check_ip_location(self) -> Tuple[bool, Optional[str]]:
        """检查 IP 地理位置"""
        try:
            return self.http_client.check_ip_location()
        except Exception as e:
            self._log(f"检查 IP 地理位置失败: {e}", "error")
            return False, None

    def _create_email(self) -> bool:
        """创建邮箱"""
        try:
            self._log(f"正在创建 {self.email_service.service_type.value} 邮箱...")
            self.email_info = self.email_service.create_email()

            if not self.email_info or "email" not in self.email_info:
                self._log("创建邮箱失败: 返回信息不完整", "error")
                return False

            self.email = self.email_info["email"]
            self._log(f"成功创建邮箱: {self.email}")
            return True

        except Exception as e:
            self._log(f"创建邮箱失败: {e}", "error")
            return False

    def _start_oauth(self) -> bool:
        """开始 OAuth 流程"""
        try:
            self._log("开始 OAuth 授权流程...")
            self.oauth_start = self.oauth_manager.start_oauth()
            self._log(f"OAuth URL 已生成: {self.oauth_start.auth_url[:80]}...")
            return True
        except Exception as e:
            self._log(f"生成 OAuth URL 失败: {e}", "error")
            return False

    def _init_session(self) -> bool:
        """初始化会话"""
        try:
            self.session = self.http_client.session
            return True
        except Exception as e:
            self._log(f"初始化会话失败: {e}", "error")
            return False

    def _get_device_id(self) -> Optional[str]:
        """获取 Device ID"""
        try:
            if not self.oauth_start:
                return None

            for retry_idx in range(MAX_OAUTH_CHALLENGE_RETRIES + 1):
                response = self.session.get(
                    self.oauth_start.auth_url,
                    timeout=15
                )
                did = self.session.cookies.get("oai-did")
                if did:
                    self._log(f"Device ID: {did}")
                    return did
                body = response.text or ""
                looks_like_challenge = (
                    response.status_code == 403
                    and (
                        "Just a moment" in body
                        or "challenge-platform" in body
                        or "<title>Just a moment" in body
                    )
                )
                if looks_like_challenge and retry_idx < MAX_OAUTH_CHALLENGE_RETRIES:
                    self._log(f"OAuth 命中 Cloudflare challenge，重试 {retry_idx + 1}/{MAX_OAUTH_CHALLENGE_RETRIES}...", "warning")
                    time.sleep(1.0)
                    continue
                break
            return None

        except Exception as e:
            self._log(f"获取 Device ID 失败: {e}", "error")
            return None

    def _check_sentinel(self, did: str) -> Optional[str]:
        """检查 Sentinel 拦截"""
        try:
            if self._last_sentinel_did == did and self._last_sentinel_token:
                self._log("复用 Sentinel token")
                return self._last_sentinel_token
            try:
                ua = getattr(self.session, "headers", {}).get(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                pow_token = build_sentinel_pow_token(ua)
            except SentinelPOWError as e:
                self._log(f"Sentinel PoW 求解失败: {e}", "error")
                return None

            sen_req_body = json.dumps({"p": pow_token, "id": did, "flow": "authorize_continue"})

            response = self.http_client.post(
                OPENAI_API_ENDPOINTS["sentinel"],
                headers={
                    "origin": "https://sentinel.openai.com",
                    "referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html?sv=20260219f9f6",
                    "content-type": "application/json",
                    "accept": "application/json",
                },
                data=sen_req_body,
            )

            if response.status_code == 200:
                sen_token = response.json().get("token")
                self._log(f"Sentinel token 获取成功")
                self._last_sentinel_did = did
                self._last_sentinel_token = sen_token or ""
                self._last_sentinel_pow = pow_token
                self._last_sentinel_header = json.dumps({
                    "p": pow_token,
                    "t": "",
                    "c": sen_token or "",
                    "id": did,
                    "flow": "authorize_continue",
                })
                return sen_token
            else:
                self._log(f"Sentinel 检查失败: {response.status_code}", "warning")
                return None

        except Exception as e:
            self._log(f"Sentinel 检查异常: {e}", "warning")
            return None

    def _refresh_oauth_session_for_signup(
        self,
        headers: Dict[str, str],
        *,
        reason: str,
        rotate: bool,
        clear_cookies: bool,
    ) -> None:
        """Best-effort refresh for signup OAuth session.

        When hitting rate-limit or invalid auth step, we can try to rotate fingerprint/session,
        re-fetch oai-did, and re-run sentinel to rebuild `openai-sentinel-token`.
        """
        try:
            if rotate and hasattr(self.http_client, "rotate_fingerprint"):
                profile = self.http_client.rotate_fingerprint(clear_cookies=clear_cookies)
                self.session = self.http_client.session
                self._log(f"{reason} 切换浏览器指纹: {profile}", "warning")

            refreshed_did = self._get_device_id()
            if not refreshed_did:
                self._log(f"{reason} 刷新 did 失败，将直接重试", "warning")
                return

            refreshed_token = self._check_sentinel(refreshed_did)
            if not refreshed_token:
                self._log(f"{reason} Sentinel token 获取失败，将直接重试", "warning")
                return

            pow_token = self._last_sentinel_pow or ""
            sentinel = json.dumps(
                {
                    "p": pow_token,
                    "t": "",
                    "c": refreshed_token,
                    "id": refreshed_did,
                    "flow": "authorize_continue",
                }
            )
            headers["openai-sentinel-token"] = sentinel
            self._last_sentinel_header = sentinel
        except Exception as e:
            self._log(f"{reason} 刷新 OAuth 会话失败: {e}", "warning")

    def _submit_signup_form(self, did: str, sen_token: Optional[str], screen_hint: str = "signup") -> SignupFormResult:
        """
        提交注册表单

        Returns:
            SignupFormResult: 提交结果，包含账号状态判断
        """
        try:
            signup_body = f'{{"username":{{"value":"{self.email}","kind":"email"}},"screen_hint":"{screen_hint}"}}'

            headers = {
                "referer": "https://auth.openai.com/create-account",
                "accept": "application/json",
                "content-type": "application/json",
            }

            if sen_token:
                pow_token = self._last_sentinel_pow or ""
                sentinel = json.dumps({
                    "p": pow_token,
                    "t": "",
                    "c": sen_token,
                    "id": did,
                    "flow": "authorize_continue",
                })
                headers["openai-sentinel-token"] = sentinel
                self._last_sentinel_header = sentinel

            response = None
            current_did = did
            current_token = sen_token
            for retry_idx in range(MAX_OAUTH_CHALLENGE_RETRIES + 1):
                response = self.session.post(
                    OPENAI_API_ENDPOINTS["signup"],
                    headers=headers,
                    data=signup_body,
                )
                self._log(f"提交注册表单状态: {response.status_code}")

                if response.status_code == 200:
                    break

                body = response.text or ""
                err_code = ""
                err_msg = ""
                try:
                    data = response.json()
                    err = data.get("error") if isinstance(data, dict) else {}
                    if isinstance(err, dict):
                        err_code = (err.get("code") or "").strip()
                        err_msg = (err.get("message") or "").strip()
                except Exception:
                    pass
                looks_like_challenge = (
                    response.status_code == 403
                    and (
                        "Just a moment" in body
                        or "challenge-platform" in body
                        or "<title>Just a moment" in body
                    )
                )
                if err_code == "invalid_auth_step" and retry_idx < MAX_OAUTH_CHALLENGE_RETRIES:
                    self._log(
                        f"提交注册表单返回 invalid_auth_step，尝试刷新 OAuth 会话 {retry_idx + 1}/{MAX_OAUTH_CHALLENGE_RETRIES}...",
                        "warning",
                    )
                    # invalid_auth_step tends to require a fresh session/cookies.
                    self._refresh_oauth_session_for_signup(
                        headers,
                        reason="invalid_auth_step",
                        rotate=True,
                        clear_cookies=True,
                    )
                    time.sleep(1.0)
                    continue

                if response.status_code == 429 and retry_idx < MAX_OAUTH_CHALLENGE_RETRIES:
                    wait_seconds = 2.5 + retry_idx * 1.5
                    # Honor server hint when present.
                    try:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            wait_seconds = max(wait_seconds, float(retry_after))
                    except Exception:
                        pass
                    # Small jitter to avoid herd behavior.
                    wait_seconds += random.uniform(0, 0.5)
                    self._log(
                        f"提交注册表单触发 429，等待 {wait_seconds:.1f}s 后尝试刷新 OAuth 会话重试 {retry_idx + 1}/{MAX_OAUTH_CHALLENGE_RETRIES}...",
                        "warning",
                    )
                    time.sleep(wait_seconds)
                    # 429 is usually rate-limit: don't rotate immediately, try rotation only after first retry.
                    self._refresh_oauth_session_for_signup(
                        headers,
                        reason="429",
                        rotate=retry_idx >= 1,
                        clear_cookies=True,
                    )
                    time.sleep(1.0)
                    continue

                if looks_like_challenge and retry_idx < MAX_OAUTH_CHALLENGE_RETRIES:
                    self._log(
                        f"提交注册表单命中 Cloudflare challenge，重试 {retry_idx + 1}/{MAX_OAUTH_CHALLENGE_RETRIES}...",
                        "warning",
                    )
                    if retry_idx >= 1 and hasattr(self.http_client, "rotate_fingerprint"):
                        try:
                            profile = self.http_client.rotate_fingerprint(clear_cookies=False)
                            self.session = self.http_client.session
                            self._log(f"切换浏览器指纹: {profile}", "warning")
                            refreshed = self._check_sentinel(current_did)
                            if refreshed:
                                pow_token = self._last_sentinel_pow or ""
                                sentinel = json.dumps({
                                    "p": pow_token,
                                    "t": "",
                                    "c": refreshed,
                                    "id": current_did,
                                    "flow": "authorize_continue",
                                })
                                headers["openai-sentinel-token"] = sentinel
                                self._last_sentinel_header = sentinel
                        except Exception as e:
                            self._log(f"指纹切换失败: {e}", "warning")
                    time.sleep(1.0)
                    continue
                break

            if response is None or response.status_code != 200:
                status = response.status_code if response else "unknown"
                snippet = (response.text or "")[:200] if response else ""
                return SignupFormResult(
                    success=False,
                    error_message=f"HTTP {status}: {snippet}"
                )

            # 解析响应判断账号状态
            try:
                response_data = response.json()
                page_type = response_data.get("page", {}).get("type", "")
                self._log(f"响应页面类型: {page_type}")

                # 判断是否为已注册账号
                is_existing = page_type == OPENAI_PAGE_TYPES["EMAIL_OTP_VERIFICATION"]

                if is_existing:
                    self._log(f"检测到已注册账号，将自动切换到登录流程")
                    self._is_existing_account = True

                return SignupFormResult(
                    success=True,
                    page_type=page_type,
                    is_existing_account=is_existing,
                    response_data=response_data
                )

            except Exception as parse_error:
                self._log(f"解析响应失败: {parse_error}", "warning")
                # 无法解析，默认成功
                return SignupFormResult(success=True)

        except Exception as e:
            self._log(f"提交注册表单失败: {e}", "error")
            return SignupFormResult(success=False, error_message=str(e))

    def _register_password(self) -> Tuple[bool, Optional[str]]:
        """注册密码"""
        try:
            # 生成密码
            password = self._generate_password()
            self.password = password  # 保存密码到实例变量
            self._log(f"生成密码: {password}")

            # 提交密码注册
            register_body = json.dumps({
                "password": password,
                "username": self.email
            })

            response = self.session.post(
                OPENAI_API_ENDPOINTS["register"],
                headers={
                    "referer": "https://auth.openai.com/create-account/password",
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                data=register_body,
            )

            self._log(f"提交密码状态: {response.status_code}")

            if response.status_code != 200:
                error_text = response.text[:500]
                self._log(f"密码注册失败: {error_text}", "warning")

                # 解析错误信息，判断是否是邮箱已注册
                try:
                    error_json = response.json()
                    error_msg = error_json.get("error", {}).get("message", "")
                    error_code = error_json.get("error", {}).get("code", "")

                    # 检测邮箱已注册的情况
                    if "already" in error_msg.lower() or "exists" in error_msg.lower() or error_code == "user_exists":
                        self._log(f"邮箱 {self.email} 可能已在 OpenAI 注册过", "error")
                        # 标记此邮箱为已注册状态
                        self._mark_email_as_registered()
                except Exception:
                    pass

                return False, None
            # 解析可能的 OTP 发送地址
            try:
                reg_data = response.json() or {}
            except Exception:
                reg_data = {}
            send_url = str(reg_data.get("continue_url") or "").strip()
            send_method = str(reg_data.get("method") or "").strip().upper()
            if send_url:
                self._otp_send_url = send_url
                self._otp_send_method = send_method or "GET"
                self._log(f"使用注册响应发送 OTP: {self._otp_send_method} {send_url[:120]}...", "info")
            else:
                self._otp_send_url = None
                self._otp_send_method = None

            return True, password

        except Exception as e:
            self._log(f"密码注册失败: {e}", "error")
            return False, None

    def _mark_email_as_registered(self):
        """标记邮箱为已注册状态（用于防止重复尝试）"""
        try:
            with get_db() as db:
                # 检查是否已存在该邮箱的记录
                existing = crud.get_account_by_email(db, self.email)
                if not existing:
                    # 创建一个失败记录，标记该邮箱已注册过
                    crud.create_account(
                        db,
                        email=self.email,
                        password="",  # 空密码表示未成功注册
                        email_service=self.email_service.service_type.value,
                        email_service_id=self.email_info.get("service_id") if self.email_info else None,
                        status="failed",
                        extra_data={"register_failed_reason": "email_already_registered_on_openai"}
                    )
                    self._log(f"已在数据库中标记邮箱 {self.email} 为已注册状态")
        except Exception as e:
            logger.warning(f"标记邮箱状态失败: {e}")

    def _send_verification_code(self) -> bool:
        """发送验证码"""
        try:
            # 记录发送时间戳
            self._otp_sent_at = time.time()

            if self._otp_send_url:
                method = (self._otp_send_method or "GET").upper()
                headers = {
                    "referer": "https://auth.openai.com/create-account/password",
                    "accept": "application/json",
                }
                if method == "POST":
                    headers["content-type"] = "application/json"
                    response = self.session.post(
                        self._otp_send_url,
                        headers=headers,
                        data="{}",
                    )
                else:
                    response = self.session.get(
                        self._otp_send_url,
                        headers=headers,
                    )
            else:
                response = self.session.get(
                    OPENAI_API_ENDPOINTS["send_otp"],
                    headers={
                        "referer": "https://auth.openai.com/create-account/password",
                        "accept": "application/json",
                    },
                )

            self._log(f"验证码发送状态: {response.status_code}")
            return response.status_code == 200

        except Exception as e:
            self._log(f"发送验证码失败: {e}", "error")
            return False

    def _resend_verification_code(self) -> bool:
        """重发验证码（新接口失败后回退旧接口）"""
        try:
            response = self.session.post(
                OPENAI_API_ENDPOINTS["email_otp_resend"],
                headers={
                    "referer": "https://auth.openai.com/email-verification",
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                data="{}",
            )
            if response.status_code == 200:
                return True
            fallback = self.session.post(
                OPENAI_API_ENDPOINTS["passwordless_send_otp"],
                headers={
                    "referer": "https://auth.openai.com/email-verification",
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                data="{}",
            )
            return fallback.status_code == 200
        except Exception:
            return False

    def _get_verification_code(self) -> Optional[str]:
        """获取验证码"""
        try:
            self._log(f"正在等待邮箱 {self.email} 的验证码...")

            email_id = self.email_info.get("service_id") if self.email_info else None
            start = time.time()
            last_resend = 0.0
            resend_count = 0
            total_timeout = 120

            while True:
                elapsed = time.time() - start
                if elapsed >= total_timeout:
                    self._log("等待验证码超时", "error")
                    return None

                one_round_timeout = max(5, min(12, int(total_timeout - elapsed)))
                try:
                    code = self.email_service.get_verification_code(
                        email=self.email,
                        email_id=email_id,
                        timeout=one_round_timeout,
                        pattern=OTP_CODE_PATTERN,
                        otp_sent_at=self._otp_sent_at,
                    )
                except TypeError:
                    code = self.email_service.get_verification_code(
                        email=self.email,
                        email_id=email_id,
                        timeout=one_round_timeout,
                        pattern=OTP_CODE_PATTERN,
                    )
                except TimeoutError:
                    code = None

                if code:
                    if code in self._used_otp_codes:
                        self._log(f"验证码已使用，继续等待新验证码: {code}", "warning")
                        try:
                            refresh = getattr(self.email_service, "refresh_seen_ids", None)
                            if callable(refresh):
                                refresh()
                        except Exception:
                            pass
                        time.sleep(0.5)
                    else:
                        self._used_otp_codes.add(code)
                        self._log(f"成功获取验证码: {code}")
                        return code

                elapsed = time.time() - start
                if _should_resend_otp(elapsed, last_resend, resend_count):
                    if self._resend_verification_code():
                        last_resend = elapsed
                        resend_count += 1
                        self._log("已重发 OTP")
                    else:
                        self._log("重发 OTP 失败", "warning")

        except Exception as e:
            self._log(f"获取验证码失败: {e}", "error")
            return None

    def _validate_verification_code(self, code: str) -> bool:
        """验证验证码"""
        try:
            code_body = f'{{"code":"{code}"}}'

            response = self.session.post(
                OPENAI_API_ENDPOINTS["validate_otp"],
                headers={
                    "referer": "https://auth.openai.com/email-verification",
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                data=code_body,
            )

            self._log(f"验证码校验状态: {response.status_code}")
            return response.status_code == 200

        except Exception as e:
            self._log(f"验证验证码失败: {e}", "error")
            return False

    def _create_user_account(self) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """创建用户账户"""
        try:
            last_error = ""
            attempts = 3
            for idx in range(attempts):
                user_info = generate_random_user_info()
                self._log(f"生成用户信息: {user_info['name']}, 生日: {user_info['birthdate']}")
                create_account_body = json.dumps(user_info)

                headers = {
                    "referer": "https://auth.openai.com/about-you",
                    "accept": "application/json",
                    "content-type": "application/json",
                }
                if self._last_sentinel_header:
                    headers["openai-sentinel-token"] = self._last_sentinel_header

                response = self.session.post(
                    OPENAI_API_ENDPOINTS["create_account"],
                    headers=headers,
                    data=create_account_body,
                )

                self._log(f"账户创建状态: {response.status_code}")

                if response.status_code == 200:
                    resp_data = None
                    try:
                        resp_data = response.json()
                    except Exception:
                        resp_data = None
                        self._log(f"创建账户响应 JSON 解析失败，响应片段: {response.text[:300]}", "warning")
                    if isinstance(resp_data, dict):
                        self._log(f"创建账户响应字段: {list(resp_data.keys())}", "info")
                        continue_url = str(resp_data.get("continue_url") or resp_data.get("redirect_url") or "").strip()
                        if continue_url:
                            self._create_account_continue_url = continue_url
                            self._log(f"创建账户 continue_url: {continue_url[:120]}...", "info")
                        else:
                            self._log("创建账户响应未包含 continue_url/redirect_url", "warning")
                    elif resp_data is not None:
                        self._log(f"创建账户响应类型非字典: {type(resp_data)}", "warning")
                    else:
                        self._log(f"创建账户响应非 JSON，响应片段: {response.text[:300]}", "warning")
                    return True, None, None, resp_data

                err_code = None
                err_msg = None
                try:
                    err = (response.json() or {}).get("error") or {}
                    err_msg = str(err.get("message") or "")
                    err_code = str(err.get("code") or "") or None
                except Exception:
                    err_msg = None
                    err_code = None

                last_error = f"{response.status_code} {response.text[:200]}"
                if err_code == "registration_disallowed":
                    self._log(f"账户创建失败: {response.text[:200]}", "warning")
                    return False, err_code, err_msg or "registration_disallowed", None

                retryable = response.status_code == 400 and (
                    "failed to register username" in (err_msg or "").lower()
                    or err_code == "bad_request"
                )
                if retryable and idx < attempts - 1:
                    time.sleep(0.6)
                    continue

                self._log(f"账户创建失败: {response.text[:200]}", "warning")
                return False, err_code, err_msg or last_error, None

            return False, None, last_error, None

        except Exception as e:
            self._log(f"创建账户失败: {e}", "error")
            return False, None, str(e), None

    def _get_workspace_id(self) -> Optional[str]:
        """获取 Workspace ID"""
        try:
            auth_cookie = self.session.cookies.get("oai-client-auth-session")
            if not auth_cookie:
                self._log("未能获取到授权 Cookie", "error")
                return None

            # 解码 JWT
            import base64
            import json as json_module

            try:
                segments = auth_cookie.split(".")
                if len(segments) < 1:
                    self._log("授权 Cookie 格式错误", "error")
                    return None

                # 解码第一个 segment
                payload = segments[0]
                pad = "=" * ((4 - (len(payload) % 4)) % 4)
                decoded = base64.urlsafe_b64decode((payload + pad).encode("ascii"))
                auth_json = json_module.loads(decoded.decode("utf-8"))

                workspaces = auth_json.get("workspaces") or []
                if not workspaces:
                    self._log(f"授权 Cookie 里没有 workspace 信息，字段: {list(auth_json.keys())}", "error")
                    return None

                workspace_id = str((workspaces[0] or {}).get("id") or "").strip()
                if not workspace_id:
                    self._log("无法解析 workspace_id", "error")
                    return None

                self._log(f"Workspace ID: {workspace_id}")
                return workspace_id

            except Exception as e:
                self._log(f"解析授权 Cookie 失败: {e}", "error")
                return None

        except Exception as e:
            self._log(f"获取 Workspace ID 失败: {e}", "error")
            return None

    def _select_workspace(self, workspace_id: str) -> Optional[str]:
        """选择 Workspace"""
        try:
            select_body = f'{{"workspace_id":"{workspace_id}"}}'

            response = self.session.post(
                OPENAI_API_ENDPOINTS["select_workspace"],
                headers={
                    "referer": "https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
                    "content-type": "application/json",
                },
                data=select_body,
            )

            if response.status_code != 200:
                self._log(f"选择 workspace 失败: {response.status_code}", "error")
                self._log(f"响应: {response.text[:200]}", "warning")
                return None

            continue_url = str((response.json() or {}).get("continue_url") or "").strip()
            if not continue_url:
                self._log("workspace/select 响应里缺少 continue_url", "error")
                return None

            self._log(f"Continue URL: {continue_url[:100]}...")
            return continue_url

        except Exception as e:
            self._log(f"选择 Workspace 失败: {e}", "error")
            return None

    def _follow_redirects(self, start_url: str) -> Optional[str]:
        """跟随重定向链，寻找回调 URL"""
        try:
            current_url = start_url
            max_redirects = 6

            for i in range(max_redirects):
                self._log(f"重定向 {i+1}/{max_redirects}: {current_url[:100]}...")
                if "add-phone" in current_url or "/phone" in current_url:
                    return "PHONE_VERIFICATION_REQUIRED"

                response = self.session.get(
                    current_url,
                    allow_redirects=False,
                    timeout=15
                )

                location = response.headers.get("Location") or ""

                # 如果不是重定向状态码，停止
                if response.status_code not in [301, 302, 303, 307, 308]:
                    self._log(f"非重定向状态码: {response.status_code}")
                    break

                if not location:
                    self._log("重定向响应缺少 Location 头")
                    break

                # 构建下一个 URL
                import urllib.parse
                next_url = urllib.parse.urljoin(current_url, location)
                if "add-phone" in next_url or "/phone" in next_url:
                    return "PHONE_VERIFICATION_REQUIRED"

                # 检查是否包含回调参数
                if "code=" in next_url and "state=" in next_url:
                    self._log(f"找到回调 URL: {next_url[:100]}...")
                    return next_url

                current_url = next_url

            self._log("未能在重定向链中找到回调 URL", "error")
            return None

        except Exception as e:
            self._log(f"跟随重定向失败: {e}", "error")
            return None

    def _handle_oauth_callback(self, callback_url: str) -> Optional[Dict[str, Any]]:
        """处理 OAuth 回调"""
        try:
            if not self.oauth_start:
                self._log("OAuth 流程未初始化", "error")
                return None

            self._log("处理 OAuth 回调...")
            # 使用当前会话完成 token 兑换，确保代理/指纹一致
            import urllib.parse
            from .constants import OAUTH_TOKEN_URL, OAUTH_CLIENT_ID, OAUTH_REDIRECT_URI
            from .oauth import _jwt_claims_no_verify

            parsed = urllib.parse.urlparse(callback_url)
            query = urllib.parse.parse_qs(parsed.query)
            code = query.get("code", [""])[0]
            returned_state = query.get("state", [""])[0]
            if not code:
                self._log("回调 URL 缺少 code", "error")
                return None
            if returned_state != self.oauth_start.state:
                self._log("State 不匹配", "error")
                return None

            payload = urllib.parse.urlencode({
                "grant_type": "authorization_code",
                "client_id": OAUTH_CLIENT_ID,
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "code_verifier": self.oauth_start.code_verifier,
            })
            headers = {
                "content-type": "application/x-www-form-urlencoded",
                "accept": "application/json",
            }
            response = self.session.post(
                OAUTH_TOKEN_URL,
                data=payload,
                headers=headers,
                timeout=30,
            )
            if response.status_code != 200:
                self._log(
                    f"OAuth token 兑换失败: {response.status_code}: {response.text[:300]}",
                    "error",
                )
                return None

            token_data = response.json() or {}
            id_token = (token_data.get("id_token") or "").strip()
            access_token = (token_data.get("access_token") or "").strip()
            refresh_token = (token_data.get("refresh_token") or "").strip()
            expires_in = int(token_data.get("expires_in") or 0)

            claims = _jwt_claims_no_verify(id_token)
            auth_claims = claims.get("https://api.openai.com/auth") or {}
            account_id = str(auth_claims.get("chatgpt_account_id") or "").strip()
            name = str(claims.get("name") or "").strip()
            email = str(claims.get("email") or "").strip()

            now = int(time.time())
            expired = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + max(expires_in, 0)))
            token_info = {
                "id_token": id_token,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "account_id": account_id,
                "name": name,
                "email": email,
                "expired": expired,
            }

            self._log("OAuth 授权成功")
            return token_info

        except Exception as e:
            self._log(f"处理 OAuth 回调失败: {e}", "error")
            return None

    def _run_login_fallback(
        self,
        did: str,
        sen_token: Optional[str],
        result: Optional[RegistrationResult] = None,
        reason: str = "",
        refresh_session: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """执行登录模式 fallback，返回 (是否成功, workspace_id)"""
        reason_text = f"（{reason}）" if reason else ""
        self._log(f"尝试登录模式 fallback{reason_text}...", "warning")

        if refresh_session:
            try:
                if hasattr(self.http_client, "rotate_fingerprint"):
                    profile = self.http_client.rotate_fingerprint(clear_cookies=True)
                    self._log(f"登录 fallback 切换浏览器指纹: {profile}", "warning")
            except Exception as exc:
                self._log(f"登录 fallback 指纹切换失败: {exc}", "warning")
            if not self._init_session():
                if result:
                    result.error_message = "登录 fallback 初始化会话失败"
                return False, None
            if not self._start_oauth():
                if result:
                    result.error_message = "登录 fallback OAuth 初始化失败"
                return False, None
            new_did = self._get_device_id()
            if not new_did:
                if result:
                    result.error_message = "登录 fallback 获取 Device ID 失败"
                return False, None
            did = new_did
            sen_token = self._check_sentinel(did)

        fallback_signup = self._submit_signup_form(did, sen_token, screen_hint="login")
        if not fallback_signup.success:
            if result:
                result.error_message = "登录 fallback 提交邮箱失败"
            return False, None
        if fallback_signup.page_type == "create_account_password":
            if result:
                result.error_message = "登录流程意外进入 create_account_password，已停止以避免再次注册"
            return False, None

        self._is_existing_account = True
        if fallback_signup.page_type == "login_password":
            self._log("登录流程返回 login_password，触发 passwordless OTP", "warning")
            try:
                response = self.session.post(
                    OPENAI_API_ENDPOINTS["passwordless_send_otp"],
                    headers={
                        "referer": "https://auth.openai.com/email-verification",
                        "accept": "application/json",
                        "content-type": "application/json",
                    },
                    data="{}",
                )
                self._log(f"登录 OTP 发送状态: {response.status_code}")
                if response.status_code != 200:
                    if result:
                        result.error_message = f"登录 OTP 发送失败: {response.status_code}"
                    return False, None
            except Exception as exc:
                if result:
                    result.error_message = f"登录 OTP 发送异常: {exc}"
                return False, None
        self._otp_sent_at = time.time()
        code = self._get_verification_code()
        if not code or not self._validate_verification_code(code):
            if result:
                result.error_message = "登录 fallback 验证 OTP 失败"
            return False, None

        workspace_id = self._get_workspace_id()
        if not workspace_id:
            if result:
                result.error_message = "登录 fallback 获取 Workspace ID 失败"
            return False, None

        return True, workspace_id

    def _assess_token_health(self, access_token: str, refresh_token: str = "") -> Dict[str, Any]:
        token = str(access_token or "").strip()
        refresh = str(refresh_token or "").strip()
        if not token:
            return {"checked": False, "status": "missing_access_token"}

        refresh_result = {"attempted": False, "ok": False, "detail": ""}
        probe_token = token
        if refresh:
            refresh_result["attempted"] = True
            try:
                from .token_refresh import TokenRefreshManager
                manager = TokenRefreshManager(proxy_url=self.proxy_url)
                refreshed = manager.refresh_by_oauth_token(refresh_token=refresh)
                if refreshed.success and refreshed.access_token:
                    probe_token = refreshed.access_token
                    refresh_result["ok"] = True
                else:
                    refresh_result["detail"] = refreshed.error_message or "refresh_failed"
            except Exception as exc:
                refresh_result["detail"] = f"{type(exc).__name__}: {str(exc)[:180]}"

        subscription = {"checked": False, "status": "unknown"}
        try:
            from .payment import check_subscription_status

            class _A:
                pass

            acct = _A()
            acct.access_token = probe_token
            sub = check_subscription_status(acct, proxy=self.proxy_url)
            subscription = {"checked": True, "status": sub}
        except Exception as exc:
            subscription = {"checked": False, "status": "query_failed", "detail": str(exc)[:180]}

        return {
            "checked": True,
            "refresh": refresh_result,
            "subscription_probe": subscription,
            "probe_access_token_refreshed": probe_token != token,
        }

    def run(self) -> RegistrationResult:
        """
        执行完整的注册流程

        支持已注册账号自动登录：
        - 如果检测到邮箱已注册，自动切换到登录流程
        - 已注册账号跳过：设置密码、发送验证码、创建用户账户
        - 共用步骤：获取验证码、验证验证码、Workspace 和 OAuth 回调

        Returns:
            RegistrationResult: 注册结果
        """
        result = RegistrationResult(success=False, logs=self.logs)

        try:
            self._log("=" * 60)
            self._log("开始注册流程")
            self._log("=" * 60)

            # 1. 检查 IP 地理位置
            self._log("1. 检查 IP 地理位置...")
            ip_ok, location = self._check_ip_location()
            if not ip_ok:
                result.error_message = f"IP 地理位置不支持: {location}"
                self._log(f"IP 检查失败: {location}", "error")
                return result

            self._log(f"IP 位置: {location}")

            # 2. 创建邮箱
            self._log("2. 创建邮箱...")
            if not self._create_email():
                result.error_message = "创建邮箱失败"
                return result

            result.email = self.email

            # 3. 初始化会话
            self._log("3. 初始化会话...")
            if not self._init_session():
                result.error_message = "初始化会话失败"
                return result

            # 4. 开始 OAuth 流程
            self._log("4. 开始 OAuth 授权流程...")
            if not self._start_oauth():
                result.error_message = "开始 OAuth 流程失败"
                return result

            # 5. 获取 Device ID
            self._log("5. 获取 Device ID...")
            did = self._get_device_id()
            if not did:
                result.error_message = "获取 Device ID 失败"
                return result

            # 6. 检查 Sentinel 拦截
            self._log("6. 检查 Sentinel 拦截...")
            sen_token = self._check_sentinel(did)
            if sen_token:
                self._log("Sentinel 检查通过")
            else:
                self._log("Sentinel 检查失败或未启用", "warning")

            # 7. 提交注册表单 + 解析响应判断账号状态
            self._log("7. 提交注册表单...")
            signup_result = self._submit_signup_form(did, sen_token, screen_hint="signup")
            if not signup_result.success:
                result.error_message = f"提交注册表单失败: {signup_result.error_message}"
                return result

            # 8. [已注册账号跳过] 注册密码
            if self._is_existing_account:
                self._log("8. [已注册账号] 跳过密码设置，OTP 已自动发送")
            else:
                self._log("8. 注册密码...")
                password_ok, password = self._register_password()
                if not password_ok:
                    result.error_message = "注册密码失败"
                    return result

            # 9. [已注册账号跳过] 发送验证码
            if self._is_existing_account:
                self._log("9. [已注册账号] 跳过发送验证码，使用自动发送的 OTP")
                # 已注册账号的 OTP 在提交表单时已自动发送，记录时间戳
                self._otp_sent_at = time.time()
            else:
                self._log("9. 发送验证码...")
                if not self._send_verification_code():
                    result.error_message = "发送验证码失败"
                    return result

            # 10. 获取验证码
            self._log("10. 等待验证码...")
            code = self._get_verification_code()
            if not code:
                result.error_message = "获取验证码失败"
                return result

            # 11. 验证验证码
            self._log("11. 验证验证码...")
            if not self._validate_verification_code(code):
                result.error_message = "验证验证码失败"
                return result

            # 12. [已注册账号跳过] 创建用户账户
            callback_url: Optional[str] = None
            if self._is_existing_account:
                self._log("12. [已注册账号] 跳过创建用户账户")
            else:
                self._log("12. 创建用户账户...")
                created, err_code, err_msg, _ = self._create_user_account()
                if not created:
                    if err_code == "registration_disallowed":
                        result.error_message = f"创建用户账户失败: {err_msg or 'registration_disallowed'}"
                        return result
                    ok, workspace_id = self._run_login_fallback(
                        did, sen_token, result=result, reason="创建用户账户失败"
                    )
                    if not ok or not workspace_id:
                        return result
                    result.workspace_id = workspace_id
                    continue_url = self._select_workspace(workspace_id)
                    if not continue_url:
                        result.error_message = "登录 fallback 选择 Workspace 失败"
                        return result
                    callback_url = self._follow_redirects(continue_url)

            if not callback_url:
                # 13. 获取 Workspace ID
                self._log("13. 获取 Workspace ID...")
                workspace_id = self._get_workspace_id()
                if not workspace_id:
                    if self._create_account_continue_url:
                        self._log("未获取 workspace_id，使用 create_account continue_url fallback", "warning")
                        callback_url = self._follow_redirects(self._create_account_continue_url)
                    else:
                        result.error_message = "获取 Workspace ID 失败"
                        return result

                result.workspace_id = workspace_id

                if not callback_url:
                    # 14. 选择 Workspace
                    self._log("14. 选择 Workspace...")
                    continue_url = self._select_workspace(workspace_id)
                    if not continue_url:
                        result.error_message = "选择 Workspace 失败"
                        return result

                    # 15. 跟随重定向链
                    self._log("15. 跟随重定向链...")
                    callback_url = self._follow_redirects(continue_url)
            if callback_url == "PHONE_VERIFICATION_REQUIRED":
                ok, workspace_id = self._run_login_fallback(
                    did, sen_token, result=result, reason="手机验证", refresh_session=True
                )
                if not ok or not workspace_id:
                    result.error_message = result.error_message or "PHONE_VERIFICATION_REQUIRED"
                    return result
                result.workspace_id = workspace_id
                continue_url = self._select_workspace(workspace_id)
                callback_url = self._follow_redirects(continue_url) if continue_url else None
            if not callback_url:
                result.error_message = "跟随重定向链失败"
                return result

            # 16. 处理 OAuth 回调
            self._log("16. 处理 OAuth 回调...")
            token_info = self._handle_oauth_callback(callback_url)
            if not token_info:
                result.error_message = "处理 OAuth 回调失败"
                return result

            # 提取账户信息
            result.account_id = token_info.get("account_id", "")
            result.access_token = token_info.get("access_token", "")
            result.refresh_token = token_info.get("refresh_token", "")
            result.id_token = token_info.get("id_token", "")
            result.password = self.password or ""  # 保存密码（已注册账号为空）
            result.type = "codex"
            result.name = token_info.get("name", "") or ""
            result.expires_at = token_info.get("expired", "")
            result.registered_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            result.mode = "login" if self._is_existing_account else "register"
            result.team_upgrade = {"attempted": False, "success": False}
            result.token_health = self._assess_token_health(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
            )

            # 设置来源标记
            result.source = "login" if self._is_existing_account else "register"

            # 尝试获取 session_token 从 cookie
            session_cookie = self.session.cookies.get("__Secure-next-auth.session-token")
            if session_cookie:
                self.session_token = session_cookie
                result.session_token = session_cookie
                self._log(f"获取到 Session Token")

            # 17. 完成
            self._log("=" * 60)
            if self._is_existing_account:
                self._log("登录成功! (已注册账号)")
            else:
                self._log("注册成功!")
            self._log(f"邮箱: {result.email}")
            self._log(f"Account ID: {result.account_id}")
            self._log(f"Workspace ID: {result.workspace_id}")
            self._log("=" * 60)

            result.success = True
            token_payload = {
                "email": result.email,
                "type": result.type,
                "name": result.name,
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "id_token": result.id_token,
                "account_id": result.account_id,
                "workspace_id": result.workspace_id,
                "expires_at": result.expires_at,
                "registered_at": result.registered_at,
                "mode": result.mode,
                "team_upgrade": result.team_upgrade or {},
                "token_health": result.token_health or {},
            }
            result.metadata = {
                "email_service": self.email_service.service_type.value,
                "proxy_used": self.proxy_url,
                "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "is_existing_account": self._is_existing_account,
                "token_payload": token_payload,
            }

            return result

        except Exception as e:
            self._log(f"注册过程中发生未预期错误: {e}", "error")
            result.error_message = str(e)
            return result

    def save_to_database(self, result: RegistrationResult) -> bool:
        """
        保存注册结果到数据库

        Args:
            result: 注册结果

        Returns:
            是否保存成功
        """
        if not result.success:
            return False

        return True  # 由 account_manager 统一处理存库
