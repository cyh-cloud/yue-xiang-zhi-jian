import type { HomeModule, HomeSnapshot, ModuleId } from '@/api/types'

export const moduleOrder: ModuleId[] = [
  'agriculture',
  'ecommerce',
  'crafts',
  'simulation',
  'resources',
  'employment'
]

export const mockModules: HomeModule[] = [
  {
    id: 'agriculture',
    code: 'AG',
    title: '农业技能',
    latin: 'AGRICULTURE',
    summary: '围绕荔枝、龙眼、水产、水稻等广东产品，把农时、病害与安全用药放进同一个学习档案。',
    actionLabel: '查看农技课程',
    visual: 'field',
    source: 'mock',
    metrics: [
      { label: '产品方向', value: '6', note: '示例' },
      { label: '农时任务', value: '24', note: '示例' },
      { label: '学习周期', value: '3周' }
    ],
    items: [
      {
        title: '荔枝保果与病害识别',
        meta: '茂名 · 12课时',
        detail: '霜疫霉病识别、安全用药、采后修剪',
        tag: '果树'
      },
      {
        title: '水产养殖水质管理',
        meta: '湛江 · 8课时',
        detail: '溶氧、投喂、消毒与日常巡塘记录',
        tag: '水产'
      },
      {
        title: '水稻全程管理',
        meta: '江门 · 10课时',
        detail: '育秧、水肥、病虫害与收获成本核算',
        tag: '粮食'
      }
    ]
  },
  {
    id: 'ecommerce',
    code: 'EC',
    title: '电商运营',
    latin: 'E-COMMERCE',
    summary: '用直播间、商品页和客服场景练习农产品上行，话术生成只作为辅助，不替代真实练习。',
    actionLabel: '进入直播实训',
    visual: 'broadcast',
    source: 'mock',
    metrics: [
      { label: '直播场景', value: '5', note: '示例' },
      { label: '脚本练习', value: '18', note: '示例' },
      { label: '评分维度', value: '4' }
    ],
    items: [
      {
        title: '荔枝直播开场',
        meta: '直播实训 · 3分钟',
        detail: '产地、口感、价格与售后一次讲清',
        tag: '话术'
      },
      {
        title: '陈皮商品页',
        meta: '文案实训 · 1课时',
        detail: '卖点排序、信任凭证与购买路径',
        tag: '商品'
      },
      {
        title: '售后异议处理',
        meta: '客服实训 · 6轮',
        detail: '缺货、物流延迟、品质异议与退款',
        tag: '客服'
      }
    ]
  },
  {
    id: 'crafts',
    code: 'CR',
    title: '手工传承',
    latin: 'CRAFT HERITAGE',
    summary: '广绣、潮汕木雕、石湾陶艺、阳江漆器按入门难度拆解，先练基础动作，再接订单标准。',
    actionLabel: '选择手工方向',
    visual: 'craft',
    source: 'mock',
    metrics: [
      { label: '非遗方向', value: '4', note: '示例' },
      { label: '基础动作', value: '12', note: '示例' },
      { label: '材料清单', value: '20+' }
    ],
    items: [
      {
        title: '广绣基础针法',
        meta: '广州 · 入门',
        detail: '直针、扭针、长短针与打籽针',
        tag: '广绣'
      },
      {
        title: '潮汕木雕粗坯',
        meta: '潮汕 · 进阶',
        detail: '顺纹运刀、层级留白与安全防护',
        tag: '木雕'
      },
      {
        title: '石湾陶艺拉坯',
        meta: '佛山 · 中级',
        detail: '揉泥排气、中心定位与坯体厚度',
        tag: '陶艺'
      }
    ]
  },
  {
    id: 'simulation',
    code: 'SIM',
    title: '虚拟实训',
    latin: 'VIRTUAL TRAINING',
    summary: '先在模拟环境犯错，再下田、进直播间或上手工艺，降低真实损失与学习门槛。',
    actionLabel: '运行诊断实训',
    visual: 'lab',
    source: 'mock',
    metrics: [
      { label: '诊断作物', value: '4', note: '示例' },
      { label: '直播场景', value: '5', note: '示例' },
      { label: 'AR工序', value: '5' }
    ],
    items: [
      {
        title: '荔枝霜疫霉病诊断',
        meta: '图像诊断 · 中度',
        detail: '病果处理、排水降湿与安全用药',
        tag: '病害'
      },
      {
        title: '直播冷场处理',
        meta: '场景模拟 · 5分钟',
        detail: '话题切换、互动提问与价格解释',
        tag: '直播'
      },
      {
        title: '广绣穿针与起针',
        meta: 'AR指导 · 5步',
        detail: '动作检查、常见错误与纠正提示',
        tag: '手艺'
      }
    ]
  },
  {
    id: 'resources',
    code: 'RS',
    title: '本土资源',
    latin: 'LOCAL RESOURCES',
    summary: '把政策、案例、方言和本地资讯放在学员能找到的位置，减少到处打听的信息成本。',
    actionLabel: '打开本土档案',
    visual: 'archive',
    source: 'mock',
    metrics: [
      { label: '政策档案', value: '8', note: '示例' },
      { label: '方言支持', value: '3', note: '示例' },
      { label: '本地案例', value: '12' }
    ],
    items: [
      {
        title: '高素质农民培育政策',
        meta: '申报 · 面向广东农村学员',
        detail: '培训补贴、报名条件与县级联系入口',
        tag: '政策'
      },
      {
        title: '返乡电商创业案例',
        meta: '案例 · 潮州',
        detail: '选品、直播节奏、包装与冷链成本',
        tag: '案例'
      },
      {
        title: '粤语农技问答',
        meta: '方言 · 语音输入',
        detail: '保留地方表达，转换成可执行农事建议',
        tag: '方言'
      }
    ]
  },
  {
    id: 'employment',
    code: 'EMP',
    title: '就业对接',
    latin: 'EMPLOYMENT',
    summary: '学习和岗位互相可见：技能档案、证书、求职意向与企业求购需求在同一条链路上更新。',
    actionLabel: '查看匹配岗位',
    visual: 'network',
    source: 'mock',
    metrics: [
      { label: '在库岗位', value: '36', note: '示例' },
      { label: '求购需求', value: '14', note: '示例' },
      { label: '匹配维度', value: '5' }
    ],
    items: [
      {
        title: '农产品直播运营',
        meta: '广州 · 5-8K',
        detail: '话术脚本、场控互动、数据复盘',
        tag: '岗位'
      },
      {
        title: '果园技术员',
        meta: '茂名 · 4-7K',
        detail: '修剪、施肥、病虫害识别与记录',
        tag: '岗位'
      },
      {
        title: '荔枝礼盒采购',
        meta: '求购 · 2000斤',
        detail: '规格、糖度、包装、交付时间与验收',
        tag: '求购'
      }
    ]
  }
]

export function createMockSnapshot(): HomeSnapshot {
  return {
    modules: mockModules.map(module => ({ ...module })),
    source: 'mock',
    generatedAt: new Date().toISOString()
  }
}
