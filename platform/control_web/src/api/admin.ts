import http from './http'

// Dashboard 聚合数据
export function getDashboard() {
  return http.get('/admin/dashboard')
}

// 分页查询用户列表
export function getUsers(params: { keyword?: string; page?: number; page_size?: number }) {
  return http.get('/admin/users', { params })
}

// 更新用户欠费策略
export function updateUserBilling(id: number, data: { allow_overdraft: boolean; max_overdraft_yuan: number }) {
  return http.put(`/admin/users/${id}/billing`, data)
}

// 分页查询设备列表
export function getDevices(params: { keyword?: string; page?: number; page_size?: number }) {
  return http.get('/admin/devices', { params })
}

// 获取 NodeManager 在线会话列表
export function getNodeSessions(params?: { node_addr?: string; model?: string }) {
  return http.get('/admin/nodemanager/sessions', { params })
}

// 获取 NodeManager 在线设备统计
export function getNodeStats(params?: { node_addr?: string }) {
  return http.get('/admin/nodemanager/stats', { params })
}

// 获取 NodeManager 节点列表
export function getNodeManagers() {
  return http.get('/admin/nodemanagers')
}

// ─── 模型仓库管理 ───

// 分页查询模型列表
export function getModels(params: { keyword?: string; page?: number; page_size?: number }) {
  return http.get('/admin/models', { params })
}

// 获取所有已启用的模型（用于分配弹窗）
export function getEnabledModels() {
  return http.get('/admin/models/enabled')
}

// 创建模型
export function createModel(data: Record<string, any>) {
  return http.post('/admin/models', data)
}

// 更新模型
export function updateModel(id: number, data: Record<string, any>) {
  return http.put(`/admin/models/${id}`, data)
}

// 删除模型
export function deleteModel(id: number) {
  return http.delete(`/admin/models/${id}`)
}

// ─── 设备模型分配 ───

// 查询设备已分配的模型列表
export function getDeviceAssignments(deviceID: number) {
  return http.get(`/admin/devices/assignments/${deviceID}`)
}

// 为单台设备分配模型
export function assignModelsToDevice(data: { device_id: number; model_ids: number[] }) {
  return http.post('/admin/devices/assign', data)
}

// 批量为多台设备分配模型
export function batchAssignModels(data: { device_ids: number[]; model_ids: number[] }) {
  return http.post('/admin/devices/batch-assign', data)
}
