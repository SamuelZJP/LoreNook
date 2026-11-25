import { request, type Schemas } from '@/api/client'

export type DemoStatus = Schemas['DemoStatus']
export type RedeemResult = Schemas['RedeemResult']

export const demoApi = {
  redeem: (token: string) => request<RedeemResult>('/api/demo/redeem', { method: 'POST', body: { token } }),
  status: () => request<DemoStatus>('/api/demo/status'),
}
