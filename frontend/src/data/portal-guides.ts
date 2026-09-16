import type { UserRole } from '@/api/types'

export type PortalId =
  | 'student'
  | 'teacher'
  | 'enterprise'
  | 'government'
  | 'admin'

export interface PortalGuideStep {
  selector: string
  title: string
  description: string
}

export interface PortalEntry {
  id: string
  title: string
  description: string
  href?: string
}

export interface PortalDefinition {
  title: string
  description: string
  entries: PortalEntry[]
  steps: PortalGuideStep[]
}

export const rolePortal: Record<UserRole, PortalId> = {
  student: 'student',
  teacher: 'teacher',
  enterprise: 'enterprise',
  government: 'government',
  super_admin: 'admin',
  admin: 'admin'
}

export const portalDefinitions: Record<PortalId, PortalDefinition> = {
  student: {
    title: '学员门户',
    description: '课程学习、个人资料与学习方向功能的集中入口。',
    entries: [
      {
        id: 'student-courses',
        title: '课程聚合',
        description: '浏览农业、电商与手工方向的已上架课程。',
        href: '/student/courses'
      },
      {
        id: 'student-profile',
        title: '个人资料',
        description: '维护联系方式、学习方向与兴趣标签。',
        href: '/student/profile'
      },
      {
        id: 'student-learning-direction',
        title: '学习方向入口',
        description: '进入农业、电商与手工方向的专属内容。'
      },
      {
        id: 'student-messages',
        title: '消息中心',
        description: '查看私信、系统通知与未读消息。',
        href: '/messages'
      },
      {
        id: 'student-agri-skills',
        title: '农业技能',
        description: '农时日历、农技问答、病虫害诊断与农业课程。',
        href: '/student/agri-skills'
      }
    ],
    steps: [
      {
        selector: '#student-courses',
        title: '课程聚合',
        description: '这里统一展示已上架课程。'
      },
      {
        selector: '#student-profile',
        title: '个人资料',
        description: '在这里维护联系方式、学习方向与兴趣标签。'
      },
      {
        selector: '#student-learning-direction',
        title: '学习方向入口',
        description: '从学习方向入口进入对应的专属内容。'
      }
    ]
  },
  teacher: {
    title: '教师工作台',
    description: '课程发布、教学公告与教学数据功能的集中入口。',
    entries: [
      {
        id: 'teacher-course-publish',
        title: '课程发布',
        description: '创建课程、维护课程内容与发布状态。'
      },
      {
        id: 'teacher-announcement',
        title: '教学公告',
        description: '向学员发布教学安排与课程通知。'
      },
      {
        id: 'teacher-dashboard',
        title: '数据看板',
        description: '查看课程与教学活动的数据概览。'
      },
      {
        id: 'teacher-messages',
        title: '消息中心',
        description: '查看私信、系统通知与未读消息。',
        href: '/messages'
      }
    ],
    steps: [
      {
        selector: '#teacher-course-publish',
        title: '课程发布',
        description: '在这里创建和管理课程。'
      },
      {
        selector: '#teacher-announcement',
        title: '教学公告',
        description: '在这里发布教学安排与通知。'
      },
      {
        selector: '#teacher-dashboard',
        title: '数据看板',
        description: '在这里查看教学数据概览。'
      }
    ]
  },
  enterprise: {
    title: '企业门户',
    description: '职位发布、申请处理与企业经营数据功能的集中入口。',
    entries: [
      {
        id: 'enterprise-job-publish',
        title: '职位发布',
        description: '发布岗位需求并维护招聘信息。'
      },
      {
        id: 'enterprise-applications',
        title: '申请处理',
        description: '查看并处理学员投递的职位申请。'
      },
      {
        id: 'enterprise-dashboard',
        title: '企业看板',
        description: '查看岗位与申请数据的经营概览。'
      },
      {
        id: 'enterprise-messages',
        title: '消息中心',
        description: '查看私信、系统通知与未读消息。',
        href: '/messages'
      }
    ],
    steps: [
      {
        selector: '#enterprise-job-publish',
        title: '职位发布',
        description: '在这里发布和维护岗位需求。'
      },
      {
        selector: '#enterprise-applications',
        title: '申请处理',
        description: '在这里查看和处理职位申请。'
      },
      {
        selector: '#enterprise-dashboard',
        title: '企业看板',
        description: '在这里查看企业数据概览。'
      }
    ]
  },
  government: {
    title: '政务门户',
    description: '政策发布、新闻发布与政务数据功能的集中入口。',
    entries: [
      {
        id: 'government-policy-publish',
        title: '政策发布',
        description: '发布与维护面向乡村人才的扶持政策。'
      },
      {
        id: 'government-news-publish',
        title: '新闻发布',
        description: '发布地区动态与政务新闻。'
      },
      {
        id: 'government-dashboard',
        title: '政务看板',
        description: '查看政策、新闻与区域服务数据概览。'
      },
      {
        id: 'government-messages',
        title: '消息中心',
        description: '查看私信、系统通知与未读消息。',
        href: '/messages'
      }
    ],
    steps: [
      {
        selector: '#government-policy-publish',
        title: '政策发布',
        description: '在这里发布和维护扶持政策。'
      },
      {
        selector: '#government-news-publish',
        title: '新闻发布',
        description: '在这里发布地区动态与政务新闻。'
      },
      {
        selector: '#government-dashboard',
        title: '政务看板',
        description: '在这里查看政务数据概览。'
      }
    ]
  },
  admin: {
    title: '管理后台',
    description: '账号管理、内容审核与系统配置功能的集中入口。',
    entries: [
      {
        id: 'admin-accounts',
        title: '账号管理',
        description: '管理平台账号、角色与启用状态。'
      },
      {
        id: 'admin-content-review',
        title: '内容审核',
        description: '审核平台发布内容与业务信息。'
      },
      {
        id: 'admin-system-config',
        title: '系统配置',
        description: '维护平台运行参数与基础配置。'
      },
      {
        id: 'admin-messages',
        title: '消息中心',
        description: '查看私信、系统通知与未读消息。',
        href: '/messages'
      }
    ],
    steps: [
      {
        selector: '#admin-accounts',
        title: '账号管理',
        description: '在这里管理账号、角色与启用状态。'
      },
      {
        selector: '#admin-content-review',
        title: '内容审核',
        description: '在这里审核平台发布内容。'
      },
      {
        selector: '#admin-system-config',
        title: '系统配置',
        description: '在这里维护平台运行参数。'
      }
    ]
  }
}
