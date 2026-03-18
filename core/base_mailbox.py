"""邮箱池基类 - 抽象临时邮箱/收件服务"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MailboxAccount:
    email: str
    account_id: str = ""
    extra: dict = None  # 平台额外信息


class BaseMailbox(ABC):
    @abstractmethod
    def get_email(self) -> MailboxAccount:
        """获取一个可用邮箱"""
        ...

    @abstractmethod
    def wait_for_code(self, account: MailboxAccount, keyword: str = "",
                      timeout: int = 120, before_ids: set = None) -> str:
        """等待并返回6位验证码"""
        ...

    @abstractmethod
    def get_current_ids(self, account: MailboxAccount) -> set:
        """返回当前邮件 ID 集合（用于过滤旧邮件）"""
        ...


def create_mailbox(provider: str, extra: dict = None, proxy: str = None) -> 'BaseMailbox':
    """工厂方法：根据 provider 创建对应的 mailbox 实例"""
    extra = extra or {}
    if provider == "tempmail_lol":
        return TempMailLolMailbox(proxy=proxy)
    elif provider == "duckmail":
        return DuckMailMailbox(
            api_url=extra.get("duckmail_api_url", "https://www.duckmail.sbs"),
            provider_url=extra.get("duckmail_provider_url", "https://api.duckmail.sbs"),
            bearer=extra.get("duckmail_bearer", "kevin273945"),
            proxy=proxy,
        )
    elif provider == "moemail":
        return MoeMailMailbox(
            api_url=extra.get("moemail_api_url", "https://sall.cc"),
            proxy=proxy,
        )
    elif provider == "cfworker":
        return CFWorkerMailbox(
            api_url=extra.get("cfworker_api_url", ""),
            admin_token=extra.get("cfworker_admin_token", ""),
            domain=extra.get("cfworker_domain", ""),
            fingerprint=extra.get("cfworker_fingerprint", ""),
            proxy=proxy,
        )
    else:  # laoudo
        return LaoудоMailbox(
            auth_token=extra.get("laoudo_auth", ""),
            email=extra.get("laoudo_email", ""),
            account_id=extra.get("laoudo_account_id", ""),
        )


class LaoудоMailbox(BaseMailbox):
    """laoudo.com 邮箱服务"""
    def __init__(self, auth_token: str, email: str, account_id: str):
        self.auth = auth_token
        self._email = email
        self._account_id = account_id
        self.api = "https://laoudo.com/api/email"
        self._ua = "Mozilla/5.0"

    def get_email(self) -> MailboxAccount:
        return MailboxAccount(email=self._email, account_id=self._account_id)

    def get_current_ids(self, account: MailboxAccount) -> set:
        from curl_cffi import requests as curl_requests
        try:
            r = curl_requests.get(
                f"{self.api}/list",
                params={"accountId": account.account_id, "allReceive": 0,
                        "emailId": 0, "timeSort": 1, "size": 50, "type": 0},
                headers={"authorization": self.auth, "user-agent": self._ua},
                timeout=15, impersonate="chrome131"
            )
            if r.status_code == 200:
                mails = r.json().get("data", {}).get("list", []) or []
                return {m.get("id") or m.get("emailId") for m in mails if m.get("id") or m.get("emailId")}
        except Exception:
            pass
        return set()

    def wait_for_code(self, account: MailboxAccount, keyword: str = "trae",
                      timeout: int = 120, before_ids: set = None) -> str:
        import re, time
        from curl_cffi import requests as curl_requests
        seen = set(before_ids) if before_ids else set()
        start = time.time()
        h = {"authorization": self.auth, "user-agent": self._ua}
        while time.time() - start < timeout:
            try:
                r = curl_requests.get(
                    f"{self.api}/list",
                    params={"accountId": account.account_id, "allReceive": 0,
                            "emailId": 0, "timeSort": 1, "size": 50, "type": 0},
                    headers=h, timeout=15, impersonate="chrome131"
                )
                if r.status_code == 200:
                    mails = r.json().get("data", {}).get("list", []) or []
                    for mail in mails:
                        mid = mail.get("id") or mail.get("emailId")
                        if not mid or mid in seen:
                            continue
                        seen.add(mid)
                        text = (str(mail.get("subject", "")) + " " +
                                str(mail.get("content") or mail.get("html") or ""))
                        if keyword and keyword.lower() not in text.lower():
                            continue
                        m = re.search(r'(?<!#)(?<!\d)(\d{6})(?!\d)', text)
                        if m:
                            return m.group(1)
            except Exception:
                pass
            time.sleep(4)
        raise TimeoutError(f"等待验证码超时 ({timeout}s)")


class AitreMailbox(BaseMailbox):
    """mail.aitre.cc 临时邮箱"""
    def __init__(self, email: str):
        self._email = email
        self.api = "https://mail.aitre.cc/api/tempmail"

    def get_email(self) -> MailboxAccount:
        return MailboxAccount(email=self._email)

    def get_current_ids(self, account: MailboxAccount) -> set:
        import requests
        try:
            r = requests.get(f"{self.api}/emails", params={"email": account.email}, timeout=10)
            emails = r.json().get("emails", [])
            return {str(m["id"]) for m in emails if "id" in m}
        except Exception:
            return set()

    def wait_for_code(self, account: MailboxAccount, keyword: str = "trae",
                      timeout: int = 120, before_ids: set = None) -> str:
        import re, time, requests
        seen = set(before_ids) if before_ids else set()
        last_check = None
        start = time.time()
        while time.time() - start < timeout:
            params = {"email": account.email}
            if last_check:
                params["lastCheck"] = last_check
            try:
                r = requests.get(f"{self.api}/poll", params=params, timeout=10)
                data = r.json()
                last_check = data.get("lastChecked")
                if data.get("count", 0) > 0:
                    r2 = requests.get(f"{self.api}/emails", params={"email": account.email}, timeout=10)
                    for mail in r2.json().get("emails", []):
                        mid = str(mail.get("id", ""))
                        if mid in seen:
                            continue
                        seen.add(mid)
                        text = mail.get("preview", "") + mail.get("content", "")
                        if keyword and keyword.lower() not in text.lower():
                            continue
                        m = re.search(r'(?<!#)(?<!\d)(\d{6})(?!\d)', text)
                        if m:
                            return m.group(1)
            except Exception:
                pass
            time.sleep(3)
        raise TimeoutError(f"等待验证码超时 ({timeout}s)")


class TempMailLolMailbox(BaseMailbox):
    """tempmail.lol 免费临时邮箱（无需注册，自动生成）"""

    def __init__(self, proxy: str = None):
        self.api = "https://api.tempmail.lol/v2"
        self.proxy = {"http": proxy, "https": proxy} if proxy else None
        self._token = None
        self._email = None

    def get_email(self) -> MailboxAccount:
        import requests
        r = requests.post(f"{self.api}/inbox/create",
            json={},
            proxies=self.proxy, timeout=15)
        data = r.json()
        self._email = data.get("address") or data.get("email", "")
        self._token = data.get("token", "")
        return MailboxAccount(email=self._email, account_id=self._token)

    def get_current_ids(self, account: MailboxAccount) -> set:
        import requests
        try:
            r = requests.get(f"{self.api}/inbox",
                params={"token": account.account_id},
                proxies=self.proxy, timeout=10)
            return {str(m["id"]) for m in r.json().get("emails", [])}
        except Exception:
            return set()

    def wait_for_code(self, account: MailboxAccount, keyword: str = "",
                      timeout: int = 120, before_ids: set = None) -> str:
        import re, time, requests
        seen = set(before_ids or [])
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = requests.get(f"{self.api}/inbox",
                    params={"token": account.account_id},
                    proxies=self.proxy, timeout=10)
                for mail in sorted(r.json().get("emails", []), key=lambda x: x.get("date", 0), reverse=True):
                    mid = str(mail.get("id", ""))
                    if mid in seen:
                        continue
                    seen.add(mid)
                    text = mail.get("subject", "") + " " + mail.get("body", "") + " " + mail.get("html", "")
                    if keyword and keyword.lower() not in text.lower():
                        continue
                    m = re.search(r'(?<!#)(?<!\d)(\d{6})(?!\d)', text)
                    if m:
                        return m.group(1)
            except Exception:
                pass
            time.sleep(3)
        return ""


class DuckMailMailbox(BaseMailbox):
    """DuckMail 自动生成邮箱（随机创建账号）"""

    def __init__(self, api_url: str = "https://www.duckmail.sbs",
                 provider_url: str = "https://api.duckmail.sbs",
                 bearer: str = "kevin273945",
                 proxy: str = None):
        self.api = api_url.rstrip("/")
        self.provider_url = provider_url
        self.bearer = bearer
        self.proxy = {"http": proxy, "https": proxy} if proxy else None
        self._token = None
        self._address = None

    def _common_headers(self) -> dict:
        return {
            "authorization": f"Bearer {self.bearer}",
            "content-type": "application/json",
            "x-api-provider-base-url": self.provider_url,
        }

    def get_email(self) -> MailboxAccount:
        import requests, random, string
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        password = "Test" + "".join(random.choices(string.digits, k=8)) + "!"
        domain = self.provider_url.replace("https://api.", "").replace("https://", "")
        address = f"{username}@{domain}"
        # 创建账号
        r = requests.post(f"{self.api}/api/mail?endpoint=%2Faccounts",
            json={"address": address, "password": password},
            headers=self._common_headers(), proxies=self.proxy, timeout=15)
        data = r.json()
        self._address = data.get("address", address)
        # 登录获取 token
        r2 = requests.post(f"{self.api}/api/mail?endpoint=%2Ftoken",
            json={"address": self._address, "password": password},
            headers=self._common_headers(), proxies=self.proxy, timeout=15)
        self._token = r2.json().get("token", "")
        return MailboxAccount(email=self._address, account_id=self._token)

    def get_current_ids(self, account: MailboxAccount) -> set:
        import requests
        try:
            r = requests.get(f"{self.api}/api/mail?endpoint=%2Fmessages%3Fpage%3D1",
                headers={"authorization": f"Bearer {account.account_id}",
                         "x-api-provider-base-url": self.provider_url},
                proxies=self.proxy, timeout=10)
            return {str(m["id"]) for m in r.json().get("hydra:member", [])}
        except Exception:
            return set()

    def wait_for_code(self, account: MailboxAccount, keyword: str = "",
                      timeout: int = 120, before_ids: set = None) -> str:
        import re, time, requests
        seen = set(before_ids or [])
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = requests.get(f"{self.api}/api/mail?endpoint=%2Fmessages%3Fpage%3D1",
                    headers={"authorization": f"Bearer {account.account_id}",
                             "x-api-provider-base-url": self.provider_url},
                    proxies=self.proxy, timeout=10)
                msgs = r.json().get("hydra:member", [])
                for msg in msgs:
                    mid = str(msg.get("id") or msg.get("msgid") or "")
                    if mid in seen: continue
                    seen.add(mid)
                    # 请求邮件详情获取完整 text
                    try:
                        r2 = requests.get(f"{self.api}/api/mail?endpoint=%2Fmessages%2F{mid}",
                            headers={"authorization": f"Bearer {account.account_id}",
                                     "x-api-provider-base-url": self.provider_url},
                            proxies=self.proxy, timeout=10)
                        detail = r2.json()
                        body = str(detail.get("text") or "") + " " + str(detail.get("subject") or "")
                    except Exception:
                        body = str(msg.get("subject") or "")
                    body = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', body)
                    m = re.search(r"(?<!#)(?<!\d)(\d{6})(?!\d)", body)
                    if m: return m.group(1)
            except Exception:
                pass
            time.sleep(3)
        return ""


class CFWorkerMailbox(BaseMailbox):
    """Cloudflare Worker 自建临时邮箱服务"""

    def __init__(self, api_url: str, admin_token: str = "", domain: str = "",
                 fingerprint: str = "", proxy: str = None):
        self.api = api_url.rstrip("/")
        self.admin_token = admin_token
        self.domain = domain
        self.fingerprint = fingerprint
        self.proxy = {"http": proxy, "https": proxy} if proxy else None
        self._token = None

    def _headers(self) -> dict:
        h = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "x-admin-auth": self.admin_token,
        }
        if self.fingerprint:
            h["x-fingerprint"] = self.fingerprint
        return h

    def get_email(self) -> MailboxAccount:
        import requests, random, string
        name = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        payload = {"enablePrefix": True, "name": name}
        if self.domain:
            payload["domain"] = self.domain
        r = requests.post(f"{self.api}/admin/new_address",
            json=payload, headers=self._headers(),
            proxies=self.proxy, timeout=15)
        data = r.json()
        email = data.get("email", data.get("address", ""))
        token = data.get("token", data.get("jwt", ""))
        self._token = token
        return MailboxAccount(email=email, account_id=token)

    def _get_mails(self, email: str) -> list:
        import requests
        r = requests.get(f"{self.api}/admin/mails",
            params={"limit": 20, "offset": 0, "address": email},
            headers=self._headers(), proxies=self.proxy, timeout=10)
        data = r.json()
        return data.get("results", data) if isinstance(data, dict) else data

    def get_current_ids(self, account: MailboxAccount) -> set:
        try:
            mails = self._get_mails(account.email)
            return {str(m.get("id", "")) for m in mails}
        except Exception:
            return set()

    def wait_for_code(self, account: MailboxAccount, keyword: str = "",
                      timeout: int = 120, before_ids: set = None) -> str:
        import re, time
        seen = set(before_ids or [])
        start = time.time()
        while time.time() - start < timeout:
            try:
                mails = self._get_mails(account.email)
                for mail in sorted(mails, key=lambda x: x.get("id", 0), reverse=True):
                    mid = str(mail.get("id", ""))
                    if not mid or mid in seen:
                        continue
                    seen.add(mid)
                    text = str(mail.get("subject", "")) + " " + str(mail.get("raw", ""))
                    m = re.search(r'(?<!#)(?<!\d)(\d{6})(?!\d)', re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text))
                    if m:
                        return m.group(1)
            except Exception:
                pass
            time.sleep(3)
        return ""


class MoeMailMailbox(BaseMailbox):
    """MoeMail (sall.cc) 邮箱服务 - 自动注册账号并生成临时邮箱"""

    def __init__(self, api_url: str = "https://sall.cc", proxy: str = None):
        self.api = api_url.rstrip("/")
        self.proxy = {"http": proxy, "https": proxy} if proxy else None
        self._session_token = None
        self._email = None

    def _register_and_login(self) -> str:
        import requests, random, string
        s = requests.Session()
        s.proxies = self.proxy
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        s.headers.update({"user-agent": ua, "origin": self.api, "referer": f"{self.api}/zh-CN/login"})
        # 注册
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
        password = "Test" + "".join(random.choices(string.digits, k=8)) + "!"
        s.post(f"{self.api}/api/auth/register",
            json={"username": username, "password": password, "turnstileToken": ""},
            timeout=15)
        # 获取 CSRF
        csrf_r = s.get(f"{self.api}/api/auth/csrf", timeout=10)
        csrf = csrf_r.json().get("csrfToken", "")
        # 登录
        s.post(f"{self.api}/api/auth/callback/credentials",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data=f"username={username}&password={password}&csrfToken={csrf}&redirect=false&callbackUrl={self.api}",
            allow_redirects=True, timeout=15)
        # 提取 session token
        for cookie in s.cookies:
            if "session-token" in cookie.name:
                self._session_token = cookie.value
                self._session = s
                return cookie.value
        return ""

    def get_email(self) -> MailboxAccount:
        if not self._session_token:
            self._register_and_login()
        r = self._session.post(f"{self.api}/api/emails/generate",
            json={}, timeout=15)
        data = r.json()
        self._email = data.get("email", data.get("address", ""))
        email_id = data.get("id", "")
        return MailboxAccount(email=self._email, account_id=str(email_id))

    def get_current_ids(self, account: MailboxAccount) -> set:
        try:
            r = self._session.get(f"{self.api}/api/emails/{account.account_id}/messages",
                timeout=10)
            return {str(m.get("id", "")) for m in r.json().get("messages", []) or r.json() if isinstance(r.json(), list)}
        except Exception:
            return set()

    def wait_for_code(self, account: MailboxAccount, keyword: str = "",
                      timeout: int = 120, before_ids: set = None) -> str:
        import re, time
        seen = set(before_ids or [])
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = self._session.get(f"{self.api}/api/emails/{account.account_id}/messages",
                    timeout=10)
                data = r.json()
                msgs = data if isinstance(data, list) else data.get("messages", [])
                for msg in msgs:
                    mid = str(msg.get("id", ""))
                    if not mid or mid in seen: continue
                    seen.add(mid)
                    # 获取邮件详情
                    try:
                        r2 = self._session.get(f"{self.api}/api/emails/{account.account_id}/messages/{mid}",
                            timeout=10)
                        detail = r2.json()
                        body = str(detail.get("text") or detail.get("body") or "") + " " + str(detail.get("subject") or "")
                    except Exception:
                        body = str(msg.get("subject", ""))
                    body = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', body)
                    m = re.search(r'(?<!#)(?<!\d)(\d{6})(?!\d)', body)
                    if m: return m.group(1)
            except Exception:
                pass
            time.sleep(3)
        return ""
