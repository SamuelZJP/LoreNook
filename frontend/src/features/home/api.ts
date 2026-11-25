import { request } from '@/api/client'
import type { Schemas } from '@/api/client'

export type HomeInfo = Schemas['HomeInfo']

export const homeApi = {
  info: () => request<HomeInfo>('/api/public/home'),
}
