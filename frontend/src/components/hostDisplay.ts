import type { Host } from '@/types/api'

export function hostDisplayName(host: Pick<Host, 'name' | 'address'>): string {
  return host.name || host.address
}
