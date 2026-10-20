export const HOME_STATS = {
  success: true,
  stats: { farmers: 128, courses: 24, jobs: 16 },
} as const;

export const AGRICULTURE_PRODUCTS = {
  success: true,
  products: [
    { id: "lychee", name: "荔枝", icon: "apple-alt", desc: "广东特色水果" },
    { id: "longan", name: "龙眼", icon: "circle", desc: "岭南佳果" },
    { id: "citrus", name: "柑橘", icon: "lemon", desc: "广东大宗水果" },
    { id: "banana", name: "香蕉", icon: "leaf", desc: "岭南特色蕉类" },
    { id: "aquatic", name: "水产养殖", icon: "fish", desc: "鱼虾蟹贝" },
    { id: "rice", name: "水稻", icon: "seedling", desc: "主要粮食作物" },
    { id: "tea", name: "茶叶", icon: "mug-hot", desc: "广东名茶" },
    { id: "vegetable", name: "蔬菜", icon: "carrot", desc: "时令蔬菜" },
  ],
} as const;

const AGRICULTURE_SOURCE = {
  key: "CARS-LZ",
  name: "荔枝龙眼产业技术体系",
  org: "国家荔枝龙眼产业技术体系",
  doc_type: "技术资料",
  doc_no: "待核",
  url: "",
} as const;

export const AGRICULTURE_CALENDAR = {
  success: true,
  product: { id: "lychee", name: "荔枝", icon: "apple-alt" },
  year: 2026,
  month: 3,
  is_configured: true,
  dates_provisional: true,
  source_summary: {
    total: 2,
    verified: 0,
    sourced: 2,
    unsourced: 0,
    sources: [],
  },
  sources_all: [AGRICULTURE_SOURCE],
  phenophase_current: {
    id: 182,
    name: "花期",
    color: "#d9a227",
    description: "花穗抽发与开花期，重点保花保果",
  },
  phenophases: [
    {
      id: 182,
      name: "花期",
      start_month: 2,
      end_month: 3,
      color: "#d9a227",
      description: "花穗抽发与开花期，重点保花保果",
      in_month: true,
    },
  ],
  solar_terms: [
    { date: "2026-03-05", day: 5, name: "惊蛰" },
    { date: "2026-03-20", day: 20, name: "春分" },
  ],
  tasks: [
    {
      id: 435,
      date: "2026-03-15",
      day: 15,
      task_md: "03-15",
      title: "花期管理",
      category: "manage",
      category_label: "田间管理",
      priority: "high",
      icon: "spa",
      description: "疏花并关注花穗生长，减少无效花量。",
      tip: "花期谨慎使用农药，优先保护授粉昆虫。",
      phase_id: 182,
      phase_name: "花期",
      phase_color: "#d9a227",
      sort_order: 1,
      is_verified: 0,
      evidence_level: "sourced",
      date_basis: "谢花前后结合花穗状态安排，避免盛花期施药。",
      source: AGRICULTURE_SOURCE,
    },
    {
      id: 436,
      date: "2026-03-28",
      day: 28,
      task_md: "03-28",
      title: "谢花后补肥",
      category: "fertilize",
      category_label: "施肥",
      priority: "medium",
      icon: "hand-holding-heart",
      description: "补充树体营养，帮助幼果稳果。",
      tip: "薄肥勤施，避免一次施用过量。",
      phase_id: 182,
      phase_name: "花期",
      phase_color: "#d9a227",
      sort_order: 2,
      is_verified: 0,
      evidence_level: "sourced",
      date_basis: "谢花后树体营养消耗较大，应在幼果期及时补充。",
      source: AGRICULTURE_SOURCE,
    },
  ],
} as const;

export const PEST_KNOWLEDGE = {
  success: true,
  crops: [
    {
      id: "lychee",
      name: "荔枝",
      icon: "apple-alt",
      summary: "岭南特色水果",
      count: 1,
    },
  ],
  entries: [
    {
      id: "lychee-anthracnose",
      crop: "lychee",
      crop_name: "荔枝",
      crop_icon: "apple-alt",
      disease: "荔枝炭疽病",
      alias: "炭疽",
      kind: "disease",
      pathogen: "胶孢炭疽菌",
      part: "叶片与果实",
      severity: "中等",
      symptoms: ["叶尖出现褐色病斑", "潮湿时病部可见粉红色孢子"],
      occurrence: "高温高湿季节发生较重。",
      treatment: ["及时清除病枝病叶", "按登记药剂说明防治"],
      prevention: ["保持果园通风", "避免偏施氮肥"],
      registered: ["按当地登记标签执行"],
      chem_table: [],
      safety_note: "用药以当地登记标签和农技人员指导为准。",
      image: null,
      sources: [],
      is_verified: 0,
    },
  ],
  total: 1,
  stats: { crops: 1, entries: 1, with_image: 0, verified: 0 },
  disclaimer: "病虫害信息仅供参考，实际防治请结合田间调查。",
} as const;

export const AGRICULTURE_SUGGESTIONS = {
  success: true,
  suggestions: ["荔枝花期如何保花保果？", "雨后如何检查炭疽病？"],
} as const;

export const CRAFTS_LIST = {
  success: true,
  crafts: [
    {
      id: "embroidery",
      name: "广绣",
      origin: "广州",
      level: "国家级非物质文化遗产",
    },
  ],
} as const;

export const CRAFT_DETAIL = {
  success: true,
  data: {
    name: "广绣",
    origin: "广州",
    history: "广绣是岭南传统刺绣工艺，以色彩丰富、针法细密见长。",
    videos: [],
    steps: [
      {
        title: "准备工具与材料",
        desc: "准备绣架、绣针、丝线与底布。",
        tips: "先检查绣架是否稳固。",
      },
      {
        title: "起针练习",
        desc: "从基础平针开始练习走线。",
        tips: "保持针距均匀。",
      },
    ],
    purchase_guide: {
      budget: { starter: "约130-320元", advanced: "约500-900元" },
      buying_tips: "先购买基础工具，熟悉后再补充材料。",
      categories: [
        {
          key: "essential",
          label: "必买基础工具",
          desc: "入门练习需要的基础工具。",
          items: [
            {
              name: "绣架",
              price: "80-180元",
              spec: "直径30厘米",
              tip: "选择夹持稳固的款式",
              where: "本地手工艺店",
            },
          ],
        },
      ],
    },
  },
} as const;

export const RESOURCE_DIALECTS = {
  success: true,
  dialects: [
    {
      id: "cantonese",
      name: "粤语",
      region: "广州话",
      emoji: "🗣️",
      areas: "广州、佛山、深圳",
      speakers: "约7000万使用者",
    },
    {
      id: "hakka",
      name: "客家话",
      region: "梅州话",
      emoji: "🏔️",
      areas: "梅州、惠州、河源",
      speakers: "约4500万使用者",
    },
  ],
} as const;

export const RESOURCE_DIALECT_INFO = {
  success: true,
  info: {
    id: "cantonese",
    name: "粤语",
    region: "广州话",
    emoji: "🗣️",
    areas: "广州、佛山、深圳",
    speakers: "约7000万使用者",
    greeting: "你好！食咗饭未？",
    greeting_meaning: "你好！吃饭了吗？",
    features: ["九声六调", "保留古汉语词汇", "大量外来语借词"],
    phrases: [
      { dialect: "你好", mandarin: "你好", pinyin: "nei5 hou2" },
      { dialect: "多谢", mandarin: "谢谢", pinyin: "do1 ze6" },
    ],
    quick_questions: [
      "荔枝点样施肥最好？",
      "龙眼几时可以摘？",
      "香蕉点样防虫？",
      "柑橘落叶点处理？",
    ],
  },
} as const;

export const RESOURCE_CASES = {
  success: true,
  cases: [
    {
      id: 1,
      title: "梅县南福村：一颗金柚的电商逆袭",
      region: "梅州",
      location: "梅县区南福村",
      background:
        "南福村以金柚种植为主，过去主要依赖线下批发。\n\n村里组织青年学习电商运营，逐步建立稳定线上渠道。",
      description: "从线下批发走向线上品牌，带动农户稳定增收。",
      quote: "把家乡的好果子讲清楚，客户自然会回来。",
      quote_author: "南福村合作社负责人",
      stats: [
        { icon: "fa-chart-line", value: "3倍", label: "线上销售额" },
        { icon: "fa-users", value: "80+", label: "带动农户" },
      ],
      milestones: [
        {
          period: "2023",
          title: "组建电商小组",
          desc: "返乡青年与合作社共同梳理产品标准。",
        },
      ],
      sources: [
        {
          title: "梅州市乡村振兴典型案例",
          media: "梅州市人民政府",
          date: "2025-06-01",
          url: "https://example.com/case",
        },
      ],
      lessons: ["先统一品质，再讲品牌故事。"],
    },
  ],
  case_review: { approved: 1, pending: 0, rejected: 0, total: 1 },
  source_note: "案例依据公开报道与政府公开信息整理。",
  lessons_note: "借鉴点由平台根据公开材料归纳。",
} as const;

export const RESOURCE_POLICIES = {
  success: true,
  policies: [
    {
      id: 25,
      title: "农业补贴申请指南",
      summary: "耕地地力保护补贴等惠农补贴的申领要点。",
      category: "补贴",
      date: "2026-04-17",
      content: "【政策概述】\n惠农补贴按年度通知执行。",
      sources: [],
    },
    {
      id: 26,
      title: "农村电商扶持政策",
      summary: "电子商务进农村示范站与地市奖补政策汇编。",
      category: "电商",
      date: "2025-09-20",
      content: "【政策概述】\n支持农村电商公共服务体系。",
      sources: [],
    },
  ],
  source_note: "本页依据公开政策文件整理。",
  disclaimer: "本平台仅作政策索引与解读，不替代官方文件。",
} as const;

export const EMPLOYMENT_JOBS = {
  success: true,
  jobs: [
    {
      id: 501,
      title: "农产品电商运营专员",
      company: "粤乡优选（演示）",
      salary: "5K-8K",
      requirements: ["熟悉直播运营", "会基础数据分析"],
      description: "负责农产品线上店铺运营与直播策划。",
      location: "茂名",
      category: "电商运营",
      job_type: "全职",
      education: "大专",
      experience: "1年",
      company_size: "50-99人",
      industry: "农业电商",
      enterprise_id: "enterprise_demo",
      review_status: "approved",
      posted_at: "2026-10-18 09:00:00",
      source_type: "enterprise",
      is_demo: 1,
    },
  ],
  recruitments: [
    {
      key: "fixture-open",
      title: "乡村公益性岗位公开招聘",
      org: "茂名市某镇人民政府",
      region: "茂名",
      category: "基层服务",
      job_type: "公益性岗位",
      headcount: "招聘 10 人",
      education: "高中及以上",
      signup_start: "2026-10-01",
      deadline: "2026-10-31",
      signup_way: "按公告原文报名",
      publish_date: "2026-10-01",
      description: "面向就业困难人员公开招聘乡村公益性岗位。",
      sources: [
        {
          title: "官方公告",
          url: "https://example.com/recruit",
          media: "政府网站",
          date: "2026-10-01",
        },
      ],
      status: "open",
      status_label: "报名中",
      days_left: 11,
      source_type: "public_recruit",
    },
  ],
  recruit_source_note: "岗位信息来自公开渠道整理。",
  recruit_disclaimer: "岗位条件以公告原文为准，本平台不代办报名。",
  category_options: {
    enterprise: [
      { value: "农业技术", count: 0 },
      { value: "电商运营", count: 1 },
      { value: "手工工艺", count: 0 },
      { value: "乡村旅游", count: 0 },
      { value: "物流仓储", count: 0 },
    ],
    recruit: [
      { value: "基层服务", count: 1 },
      { value: "乡村治理", count: 0 },
    ],
  },
  recruit_hidden_by_salary: 0,
  enterprise_review_pending: 0,
} as const;

export const COMMUNITY_DISCUSSIONS = {
  success: true,
  discussions: [
    {
      id: 101,
      title: "荔枝花期遇到连续阴雨，如何安排田间管理？",
      content:
        "最近连续降雨，花穗容易积水。想请大家分享保花保果和病害巡查的实际经验。",
      category: "agriculture",
      user_id: "student_demo",
      user_name: "演示学员",
      is_pinned: 1,
      is_deleted: 0,
      view_count: 128,
      comment_count: 6,
      created_at: "2026-10-18 09:30:00",
    },
    {
      id: 102,
      title: "第一次做农产品直播，开场话术怎么准备？",
      content: "准备在合作社做一场金柚直播，想了解开场、产品介绍和互动环节的节奏。",
      category: "ecommerce",
      user_id: "student_demo",
      user_name: "演示学员",
      is_pinned: 0,
      is_deleted: 0,
      view_count: 76,
      comment_count: 3,
      created_at: "2026-10-17 15:20:00",
    },
  ],
  total: 2,
} as const;

export const TEACHER_STATS = {
  total_students: 32,
  certificates_earned: 18,
  completion_rate: 56,
  avg_score: 72,
  no_cert_count: 14,
} as const;

export const TEACHER_STUDENTS = {
  success: true,
  students: [
    {
      id: "student-1",
      user_id: "student_demo",
      name: "演示学员",
      class_name: "电商一班",
      direction: "电商运营",
      progress: 68,
      status: "active",
      created_at: "2026-09-20 09:00:00",
      cert_total: 4,
      cert_earned: 2,
      completion: 50,
      has_cert_data: true,
    },
    {
      id: "student-2",
      user_id: "student_two",
      name: "林晓梅",
      class_name: "农业一班",
      direction: "荔枝种植",
      progress: 42,
      status: "active",
      created_at: "2026-09-18 09:00:00",
      cert_total: 4,
      cert_earned: 1,
      completion: 25,
      has_cert_data: true,
    },
  ],
} as const;

export const GOVERNMENT_OVERVIEW = {
  success: true,
  overview: {
    policies: {
      own: { total: 12, published: 9, unpublished: 3 },
      preset: { total: 5, published: 5, unpublished: 0 },
      categories: [
        { category: "补贴", count: 6 },
        { category: "电商", count: 4 },
        { category: "非遗", count: 2 },
      ],
    },
    cases: {
      total: 8,
      approved: 6,
      pending: 1,
      rejected: 1,
      regions: [
        { region: "梅州", count: 3 },
        { region: "潮州", count: 2 },
      ],
      source_total: 18,
      avg_sources: 2.25,
      items: [
        { id: 1, title: "梅县南福村金柚案例", region: "梅州", sources: 3 },
      ],
    },
  },
} as const;

export const ENTERPRISE_STATS = {
  success: true,
  stats: { total_jobs: 6, pending_jobs: 1, total_applications: 4 },
} as const;

export const ENTERPRISE_APPLICATIONS = {
  success: true,
  applications: [
    {
      id: 11,
      user_id: "student_demo",
      job_id: 501,
      status: "pending",
      applied_at: "2026-10-18 10:00:00",
      job_title: "农产品电商运营专员",
      applicant_name: "演示学员",
      applicant_phone: "000-0000-0000",
      applicant_email: "demo@example.com",
      applicant_bio: "熟悉本地农产品。",
      resume_title: "农产品电商运营",
      resume_region: "茂名",
      resume_education: "大专",
      resume_work_years: "1年",
      resume_phone: "000-0000-0000",
      resume_email: "demo@example.com",
      resume_self_eval: "认真负责。",
      resume_skills: "直播运营",
      resume_experience: "[]",
      resume_updated_at: "2026-10-18 09:00:00",
    },
  ],
} as const;

export const OPERATOR_TASK = {
  id: 901,
  product_id: "lychee",
  product_name: "荔枝",
  phase_id: 1,
  phase_name: "花期",
  title: "花期水肥管理",
  category: "manage",
  category_label: "田间管理",
  priority: "high",
  task_md: "03-20",
  month: 3,
  icon: "tasks",
  description: "补水补肥",
  tip: "薄肥勤施",
  source_key: "CARS-LZ",
  date_basis: "花期需水需肥增加",
  is_verified: 0,
  verified_by: "",
  verified_at: "",
  is_active: 1,
  sort_order: 1,
} as const;

export const OPERATOR_ENTRY = {
  id: "pest-1",
  crop_id: "lychee",
  crop_name: "荔枝",
  disease: "荔枝蝽",
  kind: "pest",
  is_verified: 0,
  verified_by: "",
  verified_at: "",
} as const;

export const OPERATOR_PRODUCT = {
  id: "lychee",
  name: "荔枝",
  icon: "apple-alt",
  summary: "广东特色水果",
  region: "广东",
  sort_order: 1,
  is_active: 1,
} as const;

export const OPERATOR_PHENOPHASE = {
  id: 1,
  product_id: "lychee",
  name: "花期",
  start_month: 2,
  end_month: 3,
  color: "#d9a227",
  description: "花穗抽发与开花期",
  sort_order: 1,
} as const;

export const OPERATOR_SOURCE = {
  key: "CARS-LZ",
  name: "荔枝龙眼产业技术体系",
  org: "国家荔枝龙眼产业技术体系",
  doc_type: "技术资料",
  doc_no: "待核",
  url: "",
  sort_order: 1,
} as const;

export const OPERATOR_CATEGORY = {
  key: "manage",
  label: "田间管理",
  color: "#1f5e43",
  sort_order: 1,
} as const;

export const OPERATOR_PEST_CROP = {
  id: "lychee",
  name: "荔枝",
  icon: "apple-alt",
  summary: "广东特色水果",
  sort_order: 1,
} as const;

export const OPERATOR_PEST_SOURCE = {
  key: "CARS-LZ",
  name: "荔枝龙眼产业技术体系",
  org: "国家荔枝龙眼产业技术体系",
  doc_type: "技术资料",
  doc_no: "待核",
  date: "2026-01-01",
  url: "",
  sort_order: 1,
} as const;

export const ADMIN_OVERVIEW = {
  success: true,
  overview: {
    users: {
      total: 128,
      suspended: 3,
      student: 96,
      teacher: 12,
      enterprise: 9,
      government: 5,
      operator: 4,
      super_admin: 2,
    },
    reviews: {
      pending: 7,
      approved: 42,
      rejected: 5,
      oldest_pending_at: "2026-10-18 09:00:00",
      oldest_pending_days: 2,
    },
    content: {
      jobs: 24,
      jobs_published: 18,
      models: 16,
      courses: 12,
      policies: 9,
      policies_published: 8,
      announcements: 6,
      cases: 5,
    },
    pending_jobs: 4,
    pending_reviews: 7,
  },
} as const;

export const LEARNER_PROFILE = {
  success: true,
  profile: {
    basic: {
      username: "student_demo",
      name: "演示学员",
      email: "demo@example.com",
      phone: "000-0000-0000",
      bio: "关注农产品电商与乡村品牌。",
      region: "茂名",
    },
    certificates: [
      {
        name: "农产品电商运营",
        status: "earned",
        earned: true,
        progress: 100,
        date: "2026-09-01",
      },
      {
        name: "直播话术实训",
        status: "in_progress",
        earned: false,
        progress: 60,
        date: "",
      },
    ],
    points: 320,
    learning: { direction: "电商运营", progress: 68 },
    training: [
      {
        title: "农产品直播脚本",
        score: 86,
        scored: true,
        status: "graded",
        submitted_at: "2026-10-10 10:00:00",
      },
    ],
  },
} as const;

export const LEARNER_RESUME = {
  success: true,
  resume: {
    id: 1,
    user_id: "student_demo",
    title: "农产品电商运营",
    region: "茂名",
    education: "大专",
    work_years: "1年",
    phone: "000-0000-0000",
    email: "demo@example.com",
    self_eval: "认真负责，熟悉本地农产品与直播运营。",
    skills: "直播运营、店铺管理、基础数据分析",
    experience: [
      {
        company: "粤乡合作社",
        position: "运营助理",
        period: "2025-2026",
        desc: "协助农产品直播策划与店铺日常运营。",
      },
    ],
    ai_used: 0,
    ai_sections: [],
    created_at: "2026-09-01 09:00:00",
    updated_at: "2026-10-18 09:00:00",
  },
} as const;

export const LEARNER_STATS = {
  success: true,
  stats: { applied: 2, saved: 1, intents: 1, messages: 3 },
} as const;
