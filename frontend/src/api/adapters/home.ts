import { apiFetch } from '@/api/client'
import { createMockSnapshot, moduleOrder } from '@/data/mock-home'
import type {
  CourseDto,
  CraftDto,
  CropDto,
  DataSource,
  HomeItem,
  HomeModule,
  HomeSnapshot,
  JobDto,
  PolicyDto,
  ProductDto,
  ScenarioDto
} from '@/api/types'

interface Envelope {
  success: true
}

interface ProductsResponse extends Envelope {
  products: ProductDto[]
}

interface CoursesResponse extends Envelope {
  courses: CourseDto[]
}

interface CraftsResponse extends Envelope {
  crafts: CraftDto[]
}

interface CropsResponse extends Envelope {
  crops: CropDto[]
}

interface ScenariosResponse extends Envelope {
  scenarios: ScenarioDto[]
}

interface PoliciesResponse extends Envelope {
  policies: PolicyDto[]
}

interface JobsResponse extends Envelope {
  jobs: JobDto[]
}

function toItems<T>(values: T[] | undefined, mapper: (value: T) => HomeItem): HomeItem[] | undefined {
  if (!Array.isArray(values) || values.length === 0) {
    return undefined
  }

  return values.slice(0, 4).map(mapper)
}

function sourceOf(results: Array<PromiseSettledResult<unknown>>): DataSource {
  return results.some(result => result.status === 'fulfilled') ? 'live' : 'mock'
}

function withModule(
  module: HomeModule,
  items: HomeItem[] | undefined,
  source: DataSource,
  firstMetric?: { label: string; value: string }
): HomeModule {
  if (!items) {
    return module
  }

  const metrics = firstMetric
    ? [firstMetric, ...module.metrics.slice(1)]
    : module.metrics

  return {
    ...module,
    items,
    metrics,
    source
  }
}

export async function fetchHomeSnapshot(): Promise<HomeSnapshot> {
  const [products, courses, crafts, crops, scenarios, policies, jobs] = await Promise.allSettled([
    apiFetch<ProductsResponse>('/api/agriculture/products'),
    apiFetch<CoursesResponse>('/api/teacher/public-courses'),
    apiFetch<CraftsResponse>('/api/crafts/list'),
    apiFetch<CropsResponse>('/api/simulation/crops'),
    apiFetch<ScenariosResponse>('/api/simulation/scenarios'),
    apiFetch<PoliciesResponse>('/api/resources/policies'),
    apiFetch<JobsResponse>('/api/employment/jobs')
  ])

  const fallback = createMockSnapshot()
  const modules = new Map(fallback.modules.map(module => [module.id, module]))
  const agriculture = modules.get('agriculture')
  const ecommerce = modules.get('ecommerce')
  const craftModule = modules.get('crafts')
  const simulation = modules.get('simulation')
  const resources = modules.get('resources')
  const employment = modules.get('employment')

  if (agriculture) {
    const source = sourceOf([products, courses])
    const productItems =
      products.status === 'fulfilled'
        ? toItems(products.value.products, product => ({
            title: product.name,
            meta: product.desc,
            detail: '农时日历、病害识别与AI问答',
            tag: '产品'
          }))
        : undefined
    const courseItems =
      courses.status === 'fulfilled'
        ? toItems(courses.value.courses, course => ({
            title: course.title ?? course.name ?? '未命名课程',
            meta: course.category ? `${course.category} · ${course.teacher_name ?? '平台课程'}` : '平台课程',
            detail: course.description ?? '课程详情待接入',
            tag: '课程'
          }))
        : undefined

    modules.set(
      'agriculture',
      withModule(
        agriculture,
        productItems ?? courseItems,
        source,
        products.status === 'fulfilled'
          ? { label: '产品方向', value: String(products.value.products.length) }
          : undefined
      )
    )
  }

  if (ecommerce) {
    const source = sourceOf([scenarios])
    const items =
      scenarios.status === 'fulfilled'
        ? toItems(scenarios.value.scenarios, scenario => ({
            title: scenario.name,
            meta: '直播实训',
            detail: scenario.desc,
            tag: '场景'
          }))
        : undefined

    modules.set(
      'ecommerce',
      withModule(
        ecommerce,
        items,
        source,
        scenarios.status === 'fulfilled'
          ? { label: '直播场景', value: String(scenarios.value.scenarios.length) }
          : undefined
      )
    )
  }

  if (craftModule) {
    const source = sourceOf([crafts])
    const items =
      crafts.status === 'fulfilled'
        ? toItems(crafts.value.crafts, craft => ({
            title: craft.name,
            meta: `${craft.origin} · ${craft.level}`,
            detail: '工序拆解、材料清单与作品提交',
            tag: '非遗'
          }))
        : undefined

    modules.set(
      'crafts',
      withModule(
        craftModule,
        items,
        source,
        crafts.status === 'fulfilled'
          ? { label: '非遗方向', value: String(crafts.value.crafts.length) }
          : undefined
      )
    )
  }

  if (simulation) {
    const source = sourceOf([crops, scenarios])
    const items =
      crops.status === 'fulfilled'
        ? toItems(crops.value.crops, crop => ({
            title: `${crop.name}病害诊断`,
            meta: '虚拟实训',
            detail: '症状对照、处置建议与安全用药提示',
            tag: '诊断'
          }))
        : undefined

    modules.set(
      'simulation',
      withModule(
        simulation,
        items,
        source,
        crops.status === 'fulfilled'
          ? { label: '诊断作物', value: String(crops.value.crops.length) }
          : undefined
      )
    )
  }

  if (resources) {
    const source = sourceOf([policies])
    const items =
      policies.status === 'fulfilled'
        ? toItems(policies.value.policies, policy => ({
            title: policy.title ?? policy.name ?? '政策档案',
            meta: policy.region ? `${policy.region} · 政策` : '政策',
            detail: policy.summary ?? policy.description ?? '政策详情待接入',
            tag: '政策'
          }))
        : undefined

    modules.set(
      'resources',
      withModule(
        resources,
        items,
        source,
        policies.status === 'fulfilled'
          ? { label: '政策档案', value: String(policies.value.policies.length) }
          : undefined
      )
    )
  }

  if (employment) {
    const source = sourceOf([jobs])
    const items =
      jobs.status === 'fulfilled'
        ? toItems(jobs.value.jobs, job => ({
            title: job.title ?? '岗位',
            meta: [job.company, job.location, job.salary].filter(Boolean).join(' · '),
            detail: Array.isArray(job.requirements)
              ? job.requirements.slice(0, 3).join(' / ')
              : job.requirements ?? '岗位要求待接入',
            tag: '岗位'
          }))
        : undefined

    modules.set(
      'employment',
      withModule(
        employment,
        items,
        source,
        jobs.status === 'fulfilled'
          ? { label: '在库岗位', value: String(jobs.value.jobs.length) }
          : undefined
      )
    )
  }

  const orderedModules = moduleOrder.map(id => modules.get(id)).filter((module): module is HomeModule => Boolean(module))
  const liveCount = orderedModules.filter(module => module.source === 'live').length
  const source = liveCount === 0 ? 'mock' : liveCount === orderedModules.length ? 'live' : 'mixed'

  return {
    modules: orderedModules,
    source,
    generatedAt: new Date().toISOString()
  }
}
