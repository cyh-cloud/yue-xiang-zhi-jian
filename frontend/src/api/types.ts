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
  direction?: string
  status?: string | null
  interest_match?: boolean
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
