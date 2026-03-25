# Mail Provider UI Conditional Fields Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Use a shared mail provider schema so Register and Settings only show the selected provider’s fields, and add `chuleicn` / `domain_imap` options.

**Architecture:** Introduce a shared `mailProviders` module that defines options, provider metadata, and per-provider field schemas. Update Register and Settings to render provider-specific fields from this module while keeping existing payload shapes.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS.

---

### Task 1: Add shared mail provider schema module

**Files:**
- Create: `frontend/src/lib/mailProviders.ts`

**Step 1: Write the failing test**

No frontend test harness exists in `frontend/package.json`. Skip automated test creation; we’ll validate via build/lint after implementation.

**Step 2: Run test to verify it fails**

Skip (no tests). Optional sanity check before changes: `npm --prefix frontend run build` (expect current build to pass).

**Step 3: Write minimal implementation**

Create `frontend/src/lib/mailProviders.ts`:

```ts
export type MailProviderField = {
  key: string
  label: string
  placeholder?: string
  secret?: boolean
  type?: 'text' | 'number'
  options?: { label: string; value: string }[]
}

export const MAIL_PROVIDER_OPTIONS = [
  { label: 'Laoudo（固定邮箱）', value: 'laoudo' },
  { label: 'TempMail.lol（自动生成）', value: 'tempmail_lol' },
  { label: 'DuckMail（自动生成）', value: 'duckmail' },
  { label: 'MoeMail (sall.cc)', value: 'moemail' },
  { label: 'Freemail（自建 CF Worker）', value: 'freemail' },
  { label: 'CF Worker（自建域名）', value: 'cfworker' },
  { label: 'ChuleiCN（API）', value: 'chuleicn' },
  { label: 'Domain IMAP（Catch-all）', value: 'domain_imap' },
]

export const MAIL_PROVIDER_META: Record<string, { section: string; desc: string }> = {
  laoudo: { section: 'Laoudo', desc: '固定邮箱，手动配置' },
  freemail: { section: 'Freemail', desc: '基于 Cloudflare Worker 的自建邮箱，支持管理员令牌或账号密码认证' },
  moemail: { section: 'MoeMail', desc: '自动注册账号并生成临时邮箱，默认无需配置' },
  tempmail_lol: { section: 'TempMail.lol', desc: '自动生成邮箱，无需配置，需要代理访问（CN IP 被封）' },
  duckmail: { section: 'DuckMail', desc: '自动生成邮箱，随机创建账号（默认无需配置）' },
  cfworker: { section: 'CF Worker 自建邮箱', desc: '基于 Cloudflare Worker 的自建临时邮箱服务' },
  chuleicn: { section: 'ChuleiCN', desc: '纯 API 临时邮箱服务' },
  domain_imap: { section: 'Domain IMAP', desc: 'IMAP Catch-all 邮箱接入' },
}

export const MAIL_PROVIDER_FIELDS: Record<string, MailProviderField[]> = {
  laoudo: [
    { key: 'laoudo_email', label: '邮箱地址', placeholder: 'xxx@laoudo.com' },
    { key: 'laoudo_account_id', label: 'Account ID', placeholder: '563' },
    { key: 'laoudo_auth', label: 'JWT Token', placeholder: 'eyJ...', secret: true },
  ],
  freemail: [
    { key: 'freemail_api_url', label: 'API URL', placeholder: 'https://mail.example.com' },
    { key: 'freemail_admin_token', label: '管理员令牌', secret: true },
    { key: 'freemail_username', label: '用户名（可选）', placeholder: '' },
    { key: 'freemail_password', label: '密码（可选）', secret: true },
  ],
  moemail: [
    { key: 'moemail_api_url', label: 'API URL', placeholder: 'https://sall.cc' },
  ],
  tempmail_lol: [],
  duckmail: [
    { key: 'duckmail_api_url', label: 'Web URL', placeholder: 'https://www.duckmail.sbs' },
    { key: 'duckmail_provider_url', label: 'Provider URL', placeholder: 'https://api.duckmail.sbs' },
    { key: 'duckmail_bearer', label: 'Bearer Token', placeholder: 'kevin273945', secret: true },
  ],
  cfworker: [
    { key: 'cfworker_api_url', label: 'API URL', placeholder: 'https://apimail.example.com' },
    { key: 'cfworker_admin_token', label: '管理员 Token', secret: true },
    { key: 'cfworker_domain', label: '邮箱域名', placeholder: 'example.com' },
    { key: 'cfworker_fingerprint', label: 'Fingerprint', placeholder: '6703363b...' },
  ],
  chuleicn: [
    { key: 'chuleicn_api_url', label: 'API URL', placeholder: 'https://mailapi.chuleicn.com' },
    { key: 'chuleicn_password', label: '密码', secret: true },
    { key: 'chuleicn_domain', label: '域名', placeholder: 'chuleicn.com' },
  ],
  domain_imap: [
    { key: 'domain_imap_host', label: 'IMAP Host', placeholder: 'imap.example.com' },
    { key: 'domain_imap_port', label: 'IMAP Port', placeholder: '993', type: 'number' },
    { key: 'domain_imap_user', label: 'IMAP User', placeholder: 'catchall@example.com' },
    { key: 'domain_imap_pass', label: 'IMAP Password', secret: true },
    {
      key: 'domain_imap_use_tls',
      label: 'Use TLS',
      options: [
        { label: '启用', value: 'true' },
        { label: '关闭', value: 'false' },
      ],
    },
    { key: 'domain_imap_proxy', label: '代理（可选）', placeholder: 'socks5://user:pass@host:port' },
    { key: 'domain_catchall_domain', label: 'Catch-all 域名', placeholder: 'example.com' },
  ],
}
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run build`  
Expected: PASS (TypeScript compiles).

**Step 5: Commit**

```bash
git add frontend/src/lib/mailProviders.ts
git commit -m "feat: add shared mail provider schema"
```

---

### Task 2: Update Register page to use shared schema + conditional fields

**Files:**
- Modify: `frontend/src/pages/Register.tsx`

**Step 1: Write the failing test**

No frontend test harness. Skip automated test creation.

**Step 2: Run test to verify it fails**

Skip (no tests).

**Step 3: Write minimal implementation**

Key changes:
- Import `MAIL_PROVIDER_OPTIONS` and `MAIL_PROVIDER_FIELDS`.
- Add missing form fields for new providers.
- Render fields via schema for the selected provider.
- Add `domain_imap` and `chuleicn` keys to `extra`.

Example patch outline:

```ts
import { MAIL_PROVIDER_FIELDS, MAIL_PROVIDER_OPTIONS } from '@/lib/mailProviders'

// form defaults
const [form, setForm] = useState({
  // ...
  mail_provider: 'moemail',
  // existing
  laoudo_auth: '',
  laoudo_email: '',
  laoudo_account_id: '',
  cfworker_api_url: '',
  cfworker_admin_token: '',
  cfworker_domain: '',
  cfworker_fingerprint: '',
  // new
  chuleicn_api_url: 'https://mailapi.chuleicn.com',
  chuleicn_password: '',
  chuleicn_domain: 'chuleicn.com',
  domain_imap_host: '',
  domain_imap_port: 993,
  domain_imap_user: '',
  domain_imap_pass: '',
  domain_imap_use_tls: 'true',
  domain_imap_proxy: '',
  domain_catchall_domain: '',
})

// mail provider select
<Select
  label="邮箱服务"
  k="mail_provider"
  options={MAIL_PROVIDER_OPTIONS.map(o => [o.value, o.label])}
/>

// conditional fields
const providerFields = MAIL_PROVIDER_FIELDS[form.mail_provider] || []
{providerFields.map(field => (
  field.options ? (
    <Select
      key={field.key}
      label={field.label}
      k={field.key}
      options={field.options.map(o => [o.value, o.label])}
    />
  ) : (
    <Input
      key={field.key}
      label={field.label}
      k={field.key}
      placeholder={field.placeholder || ''}
      type={field.type || 'text'}
    />
  )
))}

// submit extra
extra: {
  mail_provider: form.mail_provider,
  laoudo_auth: form.laoudo_auth,
  laoudo_email: form.laoudo_email,
  laoudo_account_id: form.laoudo_account_id,
  cfworker_api_url: form.cfworker_api_url,
  cfworker_admin_token: form.cfworker_admin_token,
  cfworker_domain: form.cfworker_domain,
  cfworker_fingerprint: form.cfworker_fingerprint,
  chuleicn_api_url: form.chuleicn_api_url,
  chuleicn_password: form.chuleicn_password,
  chuleicn_domain: form.chuleicn_domain,
  domain_imap_host: form.domain_imap_host,
  domain_imap_port: form.domain_imap_port,
  domain_imap_user: form.domain_imap_user,
  domain_imap_pass: form.domain_imap_pass,
  domain_imap_use_tls: form.domain_imap_use_tls,
  domain_imap_proxy: form.domain_imap_proxy,
  domain_catchall_domain: form.domain_catchall_domain,
  yescaptcha_key: form.yescaptcha_key,
  solver_url: form.solver_url,
}
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run build`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/pages/Register.tsx
git commit -m "feat: render mail provider fields in register"
```

---

### Task 3: Update Settings page to use shared schema + conditional sections

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

**Step 1: Write the failing test**

No frontend test harness. Skip automated test creation.

**Step 2: Run test to verify it fails**

Skip (no tests).

**Step 3: Write minimal implementation**

Key changes:
- Import `MAIL_PROVIDER_OPTIONS`, `MAIL_PROVIDER_META`, `MAIL_PROVIDER_FIELDS`.
- Use `MAIL_PROVIDER_OPTIONS` for `mail_provider` select.
- Build mailbox sections dynamically from the selected provider.
- Extend `Field` to support `field.options` and `field.type`.

Example patch outline:

```ts
import {
  MAIL_PROVIDER_OPTIONS,
  MAIL_PROVIDER_META,
  MAIL_PROVIDER_FIELDS,
} from '@/lib/mailProviders'

const SELECT_FIELDS: Record<string, { label: string; value: string }[]> = {
  mail_provider: MAIL_PROVIDER_OPTIONS,
  // ...
}

function Field({ field, form, setForm, showSecret, setShowSecret }: any) {
  const { key, label, placeholder, secret, type, options } = field
  const selectOptions = options || SELECT_FIELDS[key]
  // if selectOptions exists -> render select
  // else -> input with type (default text)
}

// inside component render
const selectedProvider = form.mail_provider || MAIL_PROVIDER_OPTIONS[0].value
const providerMeta = MAIL_PROVIDER_META[selectedProvider]
const providerItems = MAIL_PROVIDER_FIELDS[selectedProvider] || []
const mailboxSections = [
  {
    section: '默认邮箱服务',
    desc: '选择注册时使用的邮箱类型',
    items: [{ key: 'mail_provider', label: '邮箱服务' }],
  },
  {
    section: providerMeta?.section || '邮箱配置',
    desc: providerMeta?.desc || '',
    items: providerItems,
  },
].filter(s => s.items)

const tabs = TABS.map(t => t.id === 'mailbox' ? { ...t, sections: mailboxSections } : t)
const tab = tabs.find(t => t.id === activeTab)!
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run build`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat: show only selected mail provider settings"
```

---

### Task 4: Manual UI verification

**Files:**
- Verify: `frontend/src/pages/Register.tsx`
- Verify: `frontend/src/pages/Settings.tsx`

**Step 1: Write the failing test**

Manual checks only (no automated tests).

**Step 2: Run test to verify it fails**

Skip.

**Step 3: Write minimal implementation**

N/A (verification only).

**Step 4: Run test to verify it passes**

Manual checks in UI:
- Register: switching `mail_provider` only shows that provider’s fields.
- Settings: “邮箱服务” tab shows only selected provider’s config block.
- `chuleicn` and `domain_imap` appear in both places.

**Step 5: Commit**

Optional: `git commit -m "chore: verify mail provider UI"`
