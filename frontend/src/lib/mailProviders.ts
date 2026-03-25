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
    { key: 'moemail_api_key', label: 'API Key', placeholder: '', secret: true },
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
    {
      key: 'domain_imap_use_dynamic_subdomain',
      label: 'Use Dynamic Subdomain',
      options: [
        { label: 'true', value: 'true' },
        { label: 'false', value: 'false' },
      ],
    },
    { key: 'domain_imap_subdomain_length', label: 'Subdomain Length', placeholder: '2', type: 'number' },
  ],
}
