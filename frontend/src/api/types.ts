export type ModuleId =
  | 'agriculture'
  | 'ecommerce'
  | 'crafts'
  | 'simulation'
  | 'resources'
  | 'employment'

export type DataSource = 'live' | 'mock'
export type SnapshotSource = DataSource | 'mixed'

export type UserRole =
  | 'student'
  | 'teacher'
  | 'enterprise'
  | 'government'
  | 'super_admin'
  | 'admin'

export interface AuthUser {
  id: number
  username: string
  name: string
  role: UserRole
}

export interface AuthSessionResponse {
  success: true
  state: 'pending' | 'active'
  user: AuthUser
  default_path: string
  next_step?: 'interest-tags'
}

export interface RegisterResponse {
  success: true
  next_step: 'interest-tags' | 'portal'
  user: AuthUser
  default_path: string
}

export type LearningDirection =
  | 'agriculture'
  | 'ecommerce'
  | 'handcraft'
  | 'comprehensive'

export interface StudentProfile {
  name: string
  contact: string
  learning_direction: LearningDirection
  tag_ids: number[]
}

export interface InterestTag {
  id: number
  group_key: 'crop' | 'skill' | 'job'
  name: string
}

export interface CourseSummary {
  id: number
  title: string
  direction: Exclude<LearningDirection, 'comprehensive'>
  summary: string
  teacher_name: string
  published_at: string
  interest_match: boolean
}

export interface MessagingSummary {
  unread_private: number
  unread_notifications: number
  unread_total: number
}

export interface MessageContact {
  id: number
  name: string
  role: UserRole
  relationship: 'teacher_student' | 'application'
}

export interface PrivateMessage {
  id: number
  conversation_id: number
  sender_id: number
  body: string
  created_at: string
  read: boolean
}

export interface ConversationSummary {
  id: number
  participant: MessageContact
  last_message: PrivateMessage | null
  unread_count: number
  updated_at: string
}

export interface SystemNotification {
  id: number
  event_type: string
  title: string
  body: string
  source_type: string | null
  source_id: string | null
  source_available: boolean
  created_at: string
  read: boolean
}

export type ApiFieldErrors = Record<string, string>

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

export interface AgriProduct {
  key: string
  name: string
  sort_order: number
}

export interface FarmingCalendar {
  product: AgriProduct
  month: number
  tasks: string[]
  management: string[]
  solar_terms: string[]
  reminder: string
  empty_state: '暂无该产品农时数据' | '当月无该产品农时' | null
}

export interface QaTurn {
  id: number
  question: string
  answer: string
  input_mode: 'text' | 'voice'
  answer_mode: 'ai' | 'local_kb'
  suggestions: string[]
  created_at: string
}

export interface QaConversation {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface DiagnosisAnswer {
  round_no: number
  question: string
  answer: string
  input_mode: 'text' | 'voice'
  ai_status: 'follow_up_required' | 'conclusion_ready'
}

export interface DiagnosisFollowup {
  id: number
  outcome: 'improved' | 'unchanged' | 'worsened'
  note: string
  created_at: string
}

export interface DiagnosisConclusion {
  cause: string
  treatment: string
}

export interface DiagnosisSession {
  id: number
  product: AgriProduct
  product_key: string
  affected_part: string
  symptoms: string[]
  status: 'in_progress' | 'completed' | 'abandoned'
  round_count: number
  conclusion: DiagnosisConclusion | null
  limited: boolean
  answers: DiagnosisAnswer[]
  followups: DiagnosisFollowup[]
  source_session_id: number | null
  source_followup_id: number | null
  source_available: boolean
  created_at: string
  updated_at: string
}

export interface DiagnosticSelfTestQuestion {
  id: string
  type: 'single_choice' | 'true_false'
  prompt: string
  options: string[]
}

export interface DiagnosticSelfTest {
  id: number
  diagnosis_session_id: number
  generation_attempts: number
  questions: DiagnosticSelfTestQuestion[]
}

export interface SelfTestResultQuestion extends DiagnosticSelfTestQuestion {
  correct: boolean
  explanation: string
}

export interface SelfTestResult {
  attempt_id: number
  score: number
  questions: SelfTestResultQuestion[]
}

export type CourseDirection = 'agriculture' | 'ecommerce' | 'handcraft'

export interface AgriculturalCourse {
  id: number
  title: string
  summary: string
  teacher_name: string
  published_at: string
  tag_ids: number[]
  duration_seconds: number | null
  media_url?: string | null
  direction?: string
  status?: string | null
  interest_match?: boolean
}

export interface ActiveLearningHeartbeat {
  segment_id: string
  heartbeat_seq: number
  active_seconds: number
  settled_seconds?: number
  closed?: boolean
  restarted: boolean
  duplicate?: boolean
}

export interface CourseProgress {
  user_id: number
  course_id: number
  duration_seconds: number | null
  furthest_position_seconds: number
  resume_position_seconds: number
  progress_percent: number
  watched_seconds: number
  completed_at: string | null
  last_viewed_at: string | null
  updated_at: string | null
  quiz_available: boolean
}

export interface CourseQuizQuestion {
  id: string
  type: 'single_choice' | 'true_false'
  prompt: string
  options: string[]
}

export interface CourseQuiz {
  course_id: number
  questions: CourseQuizQuestion[]
}

export interface CourseQuizAttempt {
  id: number
  course_id: number
  answers?: Record<string, string>
  score: number
  is_formal: boolean
  is_current: boolean
  is_latest: boolean
  questions: Array<CourseQuizQuestion & {
    correct: boolean
    explanation: string
  }>
  created_at: string
}

export interface EcommerceCourse extends AgriculturalCourse {
  direction: CourseDirection
  status: string
  interest_match: boolean
  publication_status?: string | null
  is_published?: boolean | null
  learning_direction?: string | null
  return_to?: string | null
  returnTo?: string | null
  comment_url?: string | null
}

export interface HandcraftCourse extends AgriculturalCourse {
  direction: 'handcraft'
  status: string
  interest_match: boolean
  publication_status?: string | null
  is_published?: boolean | null
  learning_direction?: string | null
  return_to?: string | null
  returnTo?: string | null
  comment_url?: string | null
}

export interface HandcraftStep {
  step_key: string
  step_no: number
  title: string
  description: string
  tips: string[]
}

export interface HandcraftMaterial {
  name: string
  reference_price: string
  purchase_channel: string
  precautions: string
  taobao_keyword: string
}

export interface HandcraftCraft {
  craft_key: string | null
  name: string | null
  sort_order: number | null
  introduction: string
  is_demo: boolean
  source_available: boolean
  status: string
  available: boolean
  unavailable_reason: string | null
  steps: HandcraftStep[]
  material_guide: HandcraftMaterial[]
}

export interface HandcraftProgress {
  user_id: number
  craft_key: string | null
  status: string
  available: boolean
  unavailable_reason: string | null
  completed_steps: number[]
  completed_step_count: number
  resume_step_no: number | null
  is_completed: boolean
  updated_at: string | null
}

export interface HandcraftStepCompletion extends HandcraftProgress {
  accepted: boolean
  reason: string | null
  step_no: number
  points_source_event_id: string | null
  points_event: Record<string, unknown> | null
  points_status: string
  points_error?: string
}

export interface HandcraftVideo {
  video_id: string
  craft_key: string | null
  title: string | null
  review_status: string | null
  source_available: boolean
  media_url: string | null
  playback_url: string | null
  version: number | null
  is_demo: boolean
  available: boolean
  status: string
  unavailable_reason: string | null
  published_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface HandcraftArGuidance {
  craft_key: string
  tool_preparation: string[]
  operating_points: string[]
  common_errors: string[]
  steps: Array<{
    step_no: number
    title: string
    instruction: string
  }>
}

export interface HandcraftPointsAccount {
  user_id: number
  balance: number
  updated_at: string | null
  awarded_today: number
  daily_limit: number
  daily_limit_reached: boolean
}

export interface HandcraftLedgerEntry {
  id: number
  user_id: number
  transaction_type: string
  source_module: string
  source_event_id: string
  delta: number
  balance_after: number
  metadata: Record<string, unknown>
  created_at: string
}

export interface HandcraftReward {
  reward_id: string
  name: string
  points_cost: number
  stock: number
  is_online: boolean
  is_demo: boolean
  source_available: boolean
  affordable: boolean
  can_redeem: boolean
  unavailable_reason: string | null
}

export interface HandcraftRewardSnapshot {
  reward_id: string
  name: string
  points_cost: number
  stock: number
  is_online: boolean
  is_demo?: boolean
  source_available?: boolean
}

export type HandcraftFulfillmentStatus =
  | 'pending'
  | 'issued'
  | 'verified'
  | 'canceled'

export interface HandcraftRedemption {
  id: number
  user_id: number
  reward_id: string
  reward_name: string
  reward: HandcraftRewardSnapshot
  points_cost: number
  request_id: string
  status: HandcraftFulfillmentStatus
  reservation_status: string | null
  created_at: string
  updated_at: string
  canceled_at: string | null
}

export interface HandcraftFulfillment {
  id: number
  redemption_id: number
  status: HandcraftFulfillmentStatus
  issued_at: string | null
  verified_at: string | null
  canceled_at: string | null
  created_at: string
  updated_at: string
}

export interface HandcraftRedemptionHistory {
  fulfillment: HandcraftFulfillment
  redemption: Pick<
    HandcraftRedemption,
    | 'id'
    | 'reward_id'
    | 'reward_name'
    | 'points_cost'
    | 'request_id'
    | 'status'
    | 'created_at'
    | 'updated_at'
  >
  stock_reservation: {
    reservation_id: string | null
    status: string | null
  }
  status: HandcraftFulfillmentStatus
  restored_points: number
}

export interface HandcraftCancellation {
  fulfillment_id: number
  redemption_id: number
  user_id: number
  status: HandcraftFulfillmentStatus
  changed: boolean
  issued_at: string | null
  verified_at: string | null
  canceled_at: string | null
  points_cost: number
  restored_points: number
  outbox_id: number | null
  notification_type: 'issued' | 'cancelled' | null
  notification: Record<string, unknown> | null
}

export interface HandcraftVerification {
  fulfillment_id: number
  redemption_id: number
  user_id: number
  status: HandcraftFulfillmentStatus
  changed: boolean
  issued_at: string | null
  verified_at: string | null
  canceled_at: string | null
  points_cost: number
  restored_points: number
  outbox_id: number | null
  notification_type: 'issued' | 'cancelled' | null
  notification: Record<string, unknown> | null
}

export interface HandcraftLearningOutcome {
  outcome_type: string
  source_id: number
  created_at: string
  source_available: boolean
  summary: string
  score: number | null
  is_formal: boolean
  archive_written: boolean
}

export interface LiveScriptVersion {
  id: number
  product_name: string
  selling_points: string[]
  price_text: string
  style: 'enthusiastic' | 'professional' | 'humorous'
  script: {
    opening: string
    product_intro: string
    interaction: string
    closing: string
  }
  is_current: boolean
  created_at: string
}

export interface SimulationScene {
  key: string
  label: string
  segments: Array<{
    key: string
    label: string
  }>
}

export interface SimulationTraining {
  id: number
  scene_key: string
  scene_label: string
  segments: Array<{
    key: string
    label: string
    text: string
  }>
  status: 'draft' | 'completed'
  scores: {
    pacing: number
    emotion: number
    interaction: number
    selling_point: number
  } | null
  suggestions: {
    pacing: string
    emotion: string
    interaction: string
    selling_point: string
  } | null
  total_score: number | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface CopyTrainingSession {
  id: number
  product_type: string
  scene: string
  status: 'case_ready' | 'critique_ready' | 'copy_ready' | 'completed'
  case: {
    copy_text: string
    is_teaching_case: true
    defect_categories?: string[]
  }
  learner_critique: string | null
  reference: {
    reference_critique: string
    consistency_score: number
    reason: string
  } | null
  optimized_prompt: string | null
  revised_copy: string | null
  optimization: {
    differences: string[]
    optimization_score: number
    evidence: string
  } | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface StorePlanObject {
  [key: string]: StorePlanValue
}

export interface StorePlanArray extends Array<StorePlanValue> {}

export type StorePlanValue =
  | string
  | number
  | boolean
  | null
  | StorePlanArray
  | StorePlanObject

export interface StorePlan {
  id: number
  store_type: string
  platform: string
  style_preference: string
  plan: {
    home_layout: StorePlanValue
    color_scheme: StorePlanValue
    detail_structure: StorePlanValue
    navigation: StorePlanValue
  }
  created_at: string
}

export type CustomerServiceSummaryPart =
  | string
  | CustomerServiceSummaryPart[]
  | { [key: string]: CustomerServiceSummaryPart }

export interface CustomerScenario {
  key: string
  label: string
  criteria: string[]
}

export interface CustomerSession {
  id: number
  scenario_key: string
  scenario_label: string
  goal_criteria: string[]
  status: 'active' | 'goal_reached' | 'completed'
  end_suggested: boolean
  turns: Array<{
    id: number
    turn_no: number
    customer_message: string
    student_reply: string | null
    analysis: {
      problem: string
      evidence: string
      suggestion: string
      criteria: Record<string, boolean>
      goal_status: 'reached' | 'not_reached'
    } | null
    created_at: string
  }>
  summary: {
    overall_performance: CustomerServiceSummaryPart
    main_problems: CustomerServiceSummaryPart
    prioritized_improvements: CustomerServiceSummaryPart
    goal_completion: CustomerServiceSummaryPart
  } | null
  confirmed_at: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export type JobReviewStatus = 'pending' | 'approved' | 'rejected'

export type ApplicationStatus =
  | 'pending'
  | 'viewed'
  | 'intent'
  | 'unsuitable'

export type EffectiveApplicationStatus = ApplicationStatus | 'closed'

export interface EnterpriseDashboard {
  active_job_count: number
  received_resume_count: number
}

export interface EnterpriseJobPayload {
  title: string
  salary: string
  location: string
  category_id: number
  description: string
}

export interface EnterpriseJob extends EnterpriseJobPayload {
  job_id: string
  enterprise_id: number
  category_name: string
  review_status: JobReviewStatus
  version: number
  rejection_opinion: string | null
  published_at: string | null
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export interface EnterpriseApplicationSummary {
  application_id: string
  student_id: number
  student_name: string
  job_id: string
  job_title: string
  submitted_at: string
  status: ApplicationStatus
  status_label: string
  status_version: number
  position_closed: boolean
  position_closed_at: string | null
  effective_status: EffectiveApplicationStatus
  effective_status_label: string
}

export interface ApplicationStatusHistory {
  sequence_no: number
  previous_status: ApplicationStatus
  new_status: ApplicationStatus
  actor_enterprise_id: number
  event_id: string
  created_at: string
}

export interface EnterpriseApplicationDetail
  extends EnterpriseApplicationSummary {
  resume_snapshot: Record<string, unknown>
  skill_profile: Record<string, unknown> | null
  skill_profile_attached: boolean
  status_history: ApplicationStatusHistory[]
}

export interface EnterpriseApplicationFilters {
  job_id?: string
  status?: ApplicationStatus
  submitted_from?: string
  submitted_to?: string
  sort?: 'submitted_desc' | 'submitted_asc'
}

export interface ResumePayload {
  education_experiences: Array<Record<string, string>>
  work_experiences: Array<Record<string, string>>
  skills: string[]
}

export interface StudentResume extends ResumePayload {
  version: number
  saved_at: string | null
  has_saved_resume: boolean
}

export interface ResumeOptimizationOffer {
  offer_id: string
  base_version: number
  suggestions: string[]
  rewritten_resume: ResumePayload | null
  status: 'offered' | 'adopted' | 'discarded'
  created_at: string
}

export type SkillCategory =
  | 'live_script'
  | 'simulation_training'
  | 'quiz_score'
  | 'learning_record'

export interface SkillOutcomeItem {
  item_id: string
  category: SkillCategory
  source_module: 'agriculture' | 'ecommerce' | 'handcraft'
  source_type: string
  title: string
  summary: string
  score: number | null
  is_formal: boolean
  occurred_at: string
  source_available: boolean
  visible: boolean
}

export interface SkillProfile {
  items: SkillOutcomeItem[]
  visible_item_ids: string[]
  summary: Record<SkillCategory, number>
}

export interface JobMatchingJob {
  job_id: string
  enterprise_id: number
  enterprise_name: string
  title: string
  salary: string
  location: string
  category_id: number
  category_name: string
  description: string
  review_status: 'approved'
  version: number
  published_at: string
  updated_at: string
  category_match_count?: number
  recent_learning?: boolean
}

export interface StudentApplication {
  application_id: string
  job_id: string
  enterprise_id: number
  enterprise_name: string
  student_id: number
  student_name: string
  job_title: string
  status: ApplicationStatus
  status_version: number
  position_closed: boolean
  position_closed_at: string | null
  effective_status: EffectiveApplicationStatus
  effective_status_label: string
  submitted_at: string
  show_closed_marker: boolean
}

export interface JobFavorite {
  job_id: string
  title: string
  enterprise_name: string
  salary: string
  location: string
  description: string
  title_snapshot: string
  enterprise_name_snapshot: string
  favorited_at: string
  closed: boolean
}

export interface GovernmentPolicy {
  id: string
  title: string
  content: string
  category_code: 'subsidy' | 'ecommerce' | 'heritage' | 'training'
    | 'certification' | 'general' | 'entrepreneurship'
  category_label: string
  status: 'active' | 'unpublished'
  view_count: number
  version: number
  published_at: string
  updated_at: string
}

export interface GovernmentNews {
  id: string
  title: string
  content: string
  category_code: 'news' | 'disaster_warning' | 'policy_update'
  category_label: string
  view_count: number
  version: number
  published_at: string
  updated_at: string
}

export interface GovernmentDashboard {
  employment: {
    active_job_count: number | null
    cumulative_application_count: number | null
    available: boolean
  }
  policy: {
    active_count: number
    unpublished_count: number
    total_count: number
    view_count: number
  }
  news: {
    total_count: number
    view_count: number
  }
}

export type TeacherCourseStatus =
  | 'draft'
  | 'pending'
  | 'published'
  | 'rejected'
  | 'offline'

export type TeacherCourseFilterStatus = TeacherCourseStatus

export type TeacherMediaSourceType = 'local_upload' | 'external_url'

export interface TeacherCoursePayload {
  title: string
  direction: CourseDirection
  summary: string
  content_tags: string[]
  duration_seconds: number
  media_source_type: TeacherMediaSourceType
  media_url: string
  expected_version?: number
}

export interface TeacherCourse {
  id: number
  title: string
  direction: CourseDirection
  status: TeacherCourseStatus
  duration_seconds: number
  media_url: string
  published_at: string | null
  summary: string
  teacher_name: string
  teacher_id: number
  media_source_type: TeacherMediaSourceType
  content_tags_json: string
  version: number
  rejection_opinion: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
  content_tags: string[]
  tag_ids: number[]
}

export interface TeacherCourseFilters {
  direction?: CourseDirection
  status?: TeacherCourseFilterStatus
}

export type TeacherQuizQuestionType = 'single_choice' | 'true_false'

export interface TeacherQuizQuestion {
  id: string
  type: TeacherQuizQuestionType
  prompt: string
  options: string[]
  answer: string
}

export interface TeacherQuiz {
  enabled?: boolean
  scoring_rule?: string
  questions: TeacherQuizQuestion[]
}

export interface TeacherQuizGeneratePayload {
  summary: string
  direction: CourseDirection
}

export interface TeacherQuizSavePayload {
  expected_version: number
  enabled: boolean
  scoring_rule: string
  questions: TeacherQuizQuestion[]
}

export interface TeacherMedia {
  media_source_type: TeacherMediaSourceType
  media_url: string
  size_bytes: number
}

export type TeacherAnnouncementDeliveryStatus =
  | 'pending'
  | 'sent'
  | 'failed'

export interface TeacherAnnouncement {
  announcement_id: string
  teacher_id: number
  title: string
  body: string
  event_id: string
  delivery_status: TeacherAnnouncementDeliveryStatus
  delivery_result: Record<string, unknown>
  created_at: string
}

export interface TeacherAnnouncementPayload {
  title: string
  body: string
}

export type TeacherCommentContentType =
  | 'course_video'
  | 'handcraft_teaching_video'

export interface ContentComment {
  comment_id: string
  content_type: string
  content_id: string
  author_id: number
  parent_comment_id: string | null
  body: string
  is_teacher_reply: boolean
  created_at: string
  updated_at: string
}

export interface TeacherComment extends ContentComment {
  content_type: TeacherCommentContentType
}

export interface TeacherCommentFilters {
  content_type?: TeacherCommentContentType
  content_id?: string
}

export type TeacherLearningDirection =
  | CourseDirection
  | 'comprehensive'

export interface TeacherDirectionStats {
  student_count: number
  average_progress: number
}

export interface TeacherDashboard {
  student_total: number
  average_progress: number
  completion_rate: number
  quiz_attempt_count: number
  quiz_average_score: number
  directions: Record<TeacherLearningDirection, TeacherDirectionStats>
}

export interface TeacherReportAggregateStats {
  student_total: number
  average_progress: number
  completion_rate: number
  quiz_attempt_count: number
  quiz_average_score: number
}

export interface TeacherRiskDirectionStats {
  student_count: number
  at_risk_count: number
  at_risk_ratio: number
}

export interface TeacherReportRiskSummary {
  student_count: number
  at_risk_count: number
  at_risk_ratio: number
  directions: Record<
    TeacherLearningDirection,
    TeacherRiskDirectionStats
  >
}

export interface TeacherReportStatsSnapshot {
  aggregate_stats: TeacherReportAggregateStats
  direction_comparison: Record<
    TeacherLearningDirection,
    TeacherDirectionStats
  >
  risk_summary: TeacherReportRiskSummary
}

export interface TeacherReportSections {
  progress_analysis: string
  direction_comparison: string
  risk_warning: string
}

export interface TeacherReport {
  report_id: string
  teacher_id: number
  created_at: string
  stats_snapshot: TeacherReportStatsSnapshot
  sections: TeacherReportSections
}

export type LocalDialectCode = 'yue' | 'hak' | 'nan'
export type PolicyCategoryCode =
  | 'subsidy'
  | 'ecommerce'
  | 'heritage'
  | 'training'
  | 'certification'
  | 'general'
  | 'entrepreneurship'
export type NewsCategoryCode =
  | 'news'
  | 'disaster_warning'
  | 'policy_update'

export interface LocalResourceCase {
  id: string
  title: string
  summary: string
  published_at: string
  updated_at: string
  is_demo: boolean
}

export interface LocalResourceCaseDetail extends LocalResourceCase {
  background: string
  journey: string
  lessons: string
}

export interface LocalResourcePolicy {
  id: string
  title: string
  content: string
  category_code: PolicyCategoryCode
  category_label: string
  published_at: string
  updated_at: string
  version: number
}

export interface LocalResourceNews {
  id: string
  title: string
  content: string
  category_code: NewsCategoryCode
  category_label: string
  published_at: string
  updated_at: string
  version: number
}

export interface PolicyCategorySubscription {
  code: PolicyCategoryCode
  label: string
  subscribed: boolean
  recommended: boolean
}

export interface PolicySubscriptionState {
  categories: PolicyCategorySubscription[]
  recommended_category_codes: PolicyCategoryCode[]
}

export type AdminConsoleRole = Extract<UserRole, 'super_admin' | 'admin'>

export interface AdminDashboardResponse {
  scope: 'platform' | 'content_operations'
  metrics: Record<string, number>
}

export type AdminDashboard = AdminDashboardResponse

export type AdminReviewContentType =
  | 'course_video'
  | 'job_position'
  | 'handcraft_teaching_video'

export type AdminReviewStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'offline'

export interface AdminReviewItem {
  content_type: AdminReviewContentType
  content_id: string
  title?: string | null
  submitter_id: number | null
  submitter_name?: string | null
  owner_id?: number | null
  owner_name?: string | null
  review_status: AdminReviewStatus
  version: number | null
  rejection_opinion: string | null
  published_at: string | null
  created_at: string | null
  updated_at: string | null
}

export type AdminReviewCounts = Record<AdminReviewContentType, number>

export interface AdminReviewQueueResponse {
  success: true
  items: AdminReviewItem[]
  counts: AdminReviewCounts
}

export interface AdminReviewActionResponse {
  success: true
  item: AdminReviewItem
}

export type AdminManagedRole =
  | 'enterprise'
  | 'government'
  | 'admin'
  | 'super_admin'

export type AdminAccountRoleFilter = AdminManagedRole | 'all'

export interface AdminAccount {
  id: number
  username: string
  name: string
  role: AdminManagedRole
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface AdminAccountsResponse {
  success: true
  accounts: AdminAccount[]
}

export interface AdminAccountResponse {
  success: true
  account: AdminAccount
}

export interface AdminAccountCreatePayload {
  role: AdminManagedRole
  username: string
  name: string
  password: string
}

export interface AdminAccountStatusPayload {
  enabled: boolean
}

export interface AdminPasswordResetResponse {
  success: true
  event_id: string
  account: AdminAccount
}

export type AdminRewardStatusFilter = 'all' | 'online' | 'offline'

export type AdminFulfillmentStatusFilter =
  | 'all'
  | 'pending'
  | 'issued'
  | 'verified'
  | 'canceled'

export type AdminRedemptionStatusFilter =
  | 'all'
  | 'pending'
  | 'issued'
  | 'verified'
  | 'canceled'

export type AdminReservationStatus = 'reserved' | 'released'

export interface AdminReward {
  reward_id: string
  name: string
  points_cost: number
  stock: number
  reserved: number
  available: number
  is_online: boolean
  is_demo: boolean
  source_available: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface AdminRewardsResponse {
  success: true
  items: AdminReward[]
  count: number
}

export interface AdminRewardWritePayload {
  name: string
  points_cost: number
  stock: number
}

export type AdminRewardCreatePayload = AdminRewardWritePayload

export interface AdminRewardUpdatePayload extends AdminRewardWritePayload {
  expected_version: number
}

export interface AdminRewardOnlinePayload {
  expected_version: number
  online: boolean
}

export interface AdminRewardResponse {
  success: true
  reward: AdminReward
}

export interface AdminRewardUserContext {
  id: number
  username: string
  name: string
  role: string
  contact: string
}

export interface AdminRewardReference {
  reward_id: string
  name: string
  points_cost: number
  snapshot?: Record<string, unknown>
}

export interface AdminStockReservation {
  reservation_id: string
  status: AdminReservationStatus | null
  quantity: number
  created_at: string | null
  released_at: string | null
}

export interface AdminFulfillmentTimestamps {
  issued_at: string | null
  verified_at: string | null
  canceled_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AdminRedemptionTimestamps {
  created_at: string | null
  updated_at: string | null
  canceled_at: string | null
}

export interface AdminFulfillment extends AdminFulfillmentTimestamps {
  id: number
  redemption_id: number
  user_id: number
  user: AdminRewardUserContext
  reward: AdminRewardReference
  points_cost: number
  request_id: string
  status: AdminFulfillmentStatusFilter
  redemption_status: AdminFulfillmentStatusFilter
  stock_reservation: AdminStockReservation | null
  restored_points: number
}

export interface AdminFulfillmentsResponse {
  success: true
  items: AdminFulfillment[]
  count: number
}

export interface AdminFulfillmentActionResult {
  fulfillment_id: number
  redemption_id: number
  user_id: number
  status: AdminFulfillmentStatusFilter
  changed: boolean
  issued_at: string | null
  verified_at: string | null
  canceled_at: string | null
  points_cost: number
  restored_points: number
}

export interface AdminFulfillmentActionResponse {
  success: true
  fulfillment: AdminFulfillmentActionResult
}

export interface AdminRedemption extends AdminRedemptionTimestamps {
  id: number
  user_id: number
  user: AdminRewardUserContext
  reward: AdminRewardReference
  points_cost: number
  request_id: string
  status: AdminRedemptionStatusFilter
  fulfillment_id: number | null
  fulfillment_status: AdminFulfillmentStatusFilter | null
  stock_reservation: AdminStockReservation | null
  restored_points: number
}

export interface AdminRedemptionsResponse {
  success: true
  items: AdminRedemption[]
  count: number
}

export interface AdminRedemptionFulfillment {
  id: number
  status: AdminFulfillmentStatusFilter
  issued_at: string | null
  verified_at: string | null
  canceled_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AdminPointsLedgerEntry {
  id: number
  user_id: number
  transaction_type: string
  source_module: string
  source_event_id: string
  delta: number
  balance_after: number
  metadata: Record<string, unknown>
  created_at: string
}

export interface AdminRedemptionDetail extends AdminRedemption {
  fulfillment: AdminRedemptionFulfillment | null
  points_ledger: AdminPointsLedgerEntry[]
}

export interface AdminRedemptionDetailResponse extends AdminRedemptionDetail {
  success: true
}

export interface AdminRewardQueueQuery {
  user: string
  reward: string
  status: AdminFulfillmentStatusFilter
  fulfillment_status: AdminFulfillmentStatusFilter
  created_from: string
  created_to: string
}
