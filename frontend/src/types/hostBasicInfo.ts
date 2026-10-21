export interface HostBasicInfoAddress {
  interface: string
  address: string
}

export interface HostBasicInfo {
  host_id: number
  version: number
  name: string
  addresses: HostBasicInfoAddress[]
}

export interface HostBasicInfoUpdate {
  version: number
  name: string
  lan_ip: string
}
