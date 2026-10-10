const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

const businessDetails = new Set([
  '分组不存在',
  '主机不存在',
  '分组中仍有主机，请先移动或删除主机',
  '记录重复或关联数据已变更，请检查后重试',
  '请填写跳板机密码',
  '请填写 SSH 密码',
  '连接信息已变更，请重新填写对应密码',
  '主机已被修改，请重新打开编辑页面',
])

const fieldNames: Record<string, string> = {
  name: '名称', address: '主机地址', group_id: '所属分组', username: '用户名', port: '端口',
  auth_type: '认证方式', password: '密码', key_path: '私钥路径', vip: 'VIP',
  proxy_address: '跳板机地址', proxy_username: '跳板机用户名', proxy_port: '跳板机端口',
  proxy_auth_type: '跳板机认证方式', proxy_password: '跳板机密码', proxy_key_path: '跳板机私钥路径',
  remark: '备注', version: '数据版本',
}

export class HttpError extends Error {}

export async function request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method || 'GET',
    headers: {
      Accept: 'application/json',
      ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
    signal: AbortSignal.timeout(8000),
  })
  if (!response.ok) {
    const body: unknown = response.headers.get('Content-Type')?.includes('application/json')
      ? await response.json()
      : null
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    if (response.status === 422 && Array.isArray(detail)) {
      const labels = detail.map((item: unknown) => {
        if (!item || typeof item !== 'object' || !('loc' in item) || !Array.isArray(item.loc)) return '表单'
        const field = item.loc[item.loc.length - 1]
        return typeof field === 'string' ? fieldNames[field] || '表单' : '表单'
      })
      throw new HttpError(`${[...new Set(labels)].join('、')}校验未通过，请检查格式及必填项。`)
    }
    const message = response.status === 404 ? '记录不存在或已被删除。'
      : response.status === 409 ? '数据存在冲突，请检查名称或关联记录。'
        : response.status === 422 ? '提交内容校验未通过，请检查必填项和格式。'
          : `请求失败（HTTP ${response.status}），请稍后重试。`
    throw new HttpError(typeof detail === 'string' && businessDetails.has(detail) ? detail : message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const get = <T>(path: string) => request<T>(path)
