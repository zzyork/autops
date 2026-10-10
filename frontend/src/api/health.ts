import type { HealthResponse } from '@/types/api'
import { get } from './http'

export const getHealth = () => get<HealthResponse>('/health')
