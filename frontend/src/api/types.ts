export type ModuleId =
  | 'agriculture'
  | 'ecommerce'
  | 'crafts'
  | 'simulation'
  | 'resources'
  | 'employment'

export type DataSource = 'live' | 'mock'
export type SnapshotSource = DataSource | 'mixed'

export interface HomeMetric {
  label: string
  value: string
  note?: string
}

export interface HomeItem {
  title: string
  meta: string
  detail: string
  tag: string
}

export interface HomeModule {
  id: ModuleId
  code: string
  title: string
  latin: string
  summary: string
  actionLabel: string
  visual: 'field' | 'broadcast' | 'craft' | 'lab' | 'archive' | 'network'
  metrics: HomeMetric[]
  items: HomeItem[]
  source: DataSource
}

export interface HomeSnapshot {
  modules: HomeModule[]
  source: SnapshotSource
  generatedAt: string
}

export interface ProductDto {
  id: string
  name: string
  icon: string
  desc: string
}

export interface CourseDto {
  id: number | string
  title?: string
  name?: string
  category?: string
  description?: string
  teacher_name?: string
}

export interface CraftDto {
  id: string
  name: string
  level: string
  origin: string
}

export interface CropDto {
  id: string
  name: string
  icon: string
}

export interface ScenarioDto {
  id: string
  name: string
  desc: string
}

export interface PolicyDto {
  id?: number | string
  title?: string
  name?: string
  region?: string
  summary?: string
  description?: string
  publish_date?: string
}

export interface JobDto {
  id: number | string
  title?: string
  company?: string
  location?: string
  salary?: string
  category?: string
  requirements?: string[] | string
}
