import { del, get, post, put } from "./client";

export interface OperatorFarmingProduct {
  id: string;
  name: string;
  icon: string;
  summary: string;
  region: string;
  sort_order: number;
  is_active: number;
}

export interface OperatorPhenophase {
  id: number;
  product_id: string;
  name: string;
  start_month: number;
  end_month: number;
  color: string | null;
  description: string;
  sort_order: number;
}

export interface OperatorFarmingSource {
  key: string;
  name: string;
  org: string;
  doc_type: string;
  doc_no: string;
  url: string;
  sort_order: number;
}

export interface OperatorFarmingCategory {
  key: string;
  label: string;
  color: string;
  sort_order: number;
}

export interface OperatorFarmingTask {
  id: number;
  product_id: string;
  product_name: string;
  phase_id: number | null;
  phase_name: string | null;
  title: string;
  category: string;
  category_label: string;
  priority: string;
  task_md: string;
  month: number;
  icon: string;
  description: string;
  tip: string;
  source_key: string;
  date_basis: string;
  is_verified: number;
  verified_by: string;
  verified_at: string;
  is_active: number;
  sort_order: number;
}

export interface OperatorPestCrop {
  id: string;
  name: string;
  icon: string;
  summary: string;
  sort_order: number;
}

export interface OperatorPestSource {
  key: string;
  name: string;
  org: string;
  doc_type: string;
  doc_no: string;
  date: string;
  url: string;
  sort_order: number;
}

export interface OperatorPestEntrySummary {
  id: string;
  crop_id: string;
  crop_name: string;
  disease: string;
  kind: string;
  is_verified: number;
  verified_by: string;
  verified_at: string;
}

export interface OperatorPestImage {
  file: string;
  credit: string;
  license: string;
  caption: string;
  source_url: string;
  shot_date: string;
  note: string;
}

export interface OperatorPestChemRow {
  agent: string;
  dose: string | number | null;
  interval_days: string | number | null;
  max_times: string | number | null;
}

export interface OperatorPestEntryDetail extends OperatorPestEntrySummary {
  crop: string;
  crop_icon: string;
  alias: string;
  pathogen: string;
  part: string;
  severity: string;
  symptoms: string[];
  occurrence: string;
  treatment: string[];
  prevention: string[];
  registered: string[];
  chem_table: OperatorPestChemRow[];
  safety_note: string;
  sources: Array<{ key: string }>;
  image: OperatorPestImage | null;
  sort_order: number;
}

export interface OperatorCraftSummary {
  id: string;
  name: string;
  origin: string;
  history: string;
  level: string;
  sort_order: number;
  step_count: number;
  item_count: number;
  has_budget: boolean;
}

export interface OperatorCraftStep {
  id: number;
  title: string;
  desc: string;
  tips: string;
  sort_order: number;
}

export interface OperatorCraftCategory {
  craft_id: string;
  key: string;
  label: string;
  desc: string;
  sort_order: number;
}

export interface OperatorCraftItem {
  id: number;
  craft_id: string;
  category_key: string;
  name: string;
  price: string;
  spec: string;
  tip: string;
  where: string;
  sort_order: number;
}

export interface OperatorCraftBudget {
  craft_id: string;
  starter: string;
  advanced: string;
  buying_tips: string;
}

export interface OperatorCraftVideo {
  id: number;
  bvid: string;
  title: string;
  author: string;
  duration: number;
  view_count: number;
  danmaku: number;
  like_count: number;
  pubdate: number;
  cover: string;
  craft_id: string;
  sort_order: number;
}

export interface OperatorDialect {
  id: string;
  name: string;
  region: string;
  emoji: string;
  areas: string;
  speakers: string;
  greeting: string;
  greeting_meaning: string;
  features: string[];
  sort_order: number;
  feature_count: number;
  phrase_count: number;
  question_count: number;
}

export interface OperatorDialectPhrase {
  id: number;
  dialect: string;
  mandarin: string;
  pinyin: string;
  sort_order: number;
}

export interface OperatorDialectQuestion {
  id: number;
  question: string;
  sort_order: number;
}

interface OperatorResult<T> {
  success: true;
  result: T;
}

interface OperatorProductsResponse {
  success: true;
  products: OperatorFarmingProduct[];
}

interface OperatorPhenophasesResponse {
  success: true;
  phenophases: OperatorPhenophase[];
}

interface OperatorFarmingSourcesResponse {
  success: true;
  sources: OperatorFarmingSource[];
}

interface OperatorFarmingCategoriesResponse {
  success: true;
  categories: OperatorFarmingCategory[];
}

interface OperatorFarmingTasksResponse {
  success: true;
  tasks: OperatorFarmingTask[];
}

interface OperatorPestCropsResponse {
  success: true;
  crops: OperatorPestCrop[];
}

interface OperatorPestSourcesResponse {
  success: true;
  sources: OperatorPestSource[];
}

interface OperatorPestEntriesResponse {
  success: true;
  entries: OperatorPestEntrySummary[];
}

interface OperatorPestEntryResponse {
  success: true;
  entry: OperatorPestEntryDetail;
}

export interface OperatorRecruitment {
  key: string;
  title: string;
  org: string;
  region: string;
  category: string;
  job_type: string;
  headcount: string;
  education: string;
  experience: string;
  salary: string;
  description: string;
  publish_date: string;
  signup_start: string;
  deadline: string;
  signup_way: string;
  contact: string;
  sort_order: number;
  source_count: number;
}

export interface OperatorRecruitmentSource {
  id: number;
  title: string;
  media: string;
  date: string;
  url: string;
  sort_order: number;
}

interface OperatorRecruitmentsResponse {
  success: true;
  recruitments: OperatorRecruitment[];
  categories: string[];
}

interface OperatorRecruitmentSourcesResponse {
  success: true;
  sources: OperatorRecruitmentSource[];
}

export interface OperatorCaseSummary {
  id: number;
  title: string;
  region: string;
  location: string;
  background: string;
  description: string;
  quote: string;
  quote_author: string;
  sort_order: number;
  stat_count: number;
  milestone_count: number;
  source_count: number;
  lesson_count: number;
}

export interface OperatorCaseStat {
  id: number;
  label: string;
  value: string;
  icon: string;
  sort_order: number;
}

export interface OperatorCaseMilestone {
  id: number;
  period: string;
  title: string;
  desc: string;
  sort_order: number;
}

export interface OperatorCaseSource {
  id: number;
  title: string;
  media: string;
  date: string;
  url: string;
  sort_order: number;
}

export interface OperatorCaseLesson {
  id: number;
  text: string;
  sort_order: number;
}

interface OperatorCasesResponse {
  success: true;
  cases: OperatorCaseSummary[];
}

interface OperatorCaseStatsResponse {
  success: true;
  stats: OperatorCaseStat[];
}

interface OperatorCaseMilestonesResponse {
  success: true;
  milestones: OperatorCaseMilestone[];
}

interface OperatorCaseSourcesResponse {
  success: true;
  sources: OperatorCaseSource[];
}

interface OperatorCaseLessonsResponse {
  success: true;
  lessons: OperatorCaseLesson[];
}

interface OperatorCraftsResponse {
  success: true;
  crafts: OperatorCraftSummary[];
}

interface OperatorCraftStepsResponse {
  success: true;
  steps: OperatorCraftStep[];
}

interface OperatorCraftCategoriesResponse {
  success: true;
  categories: OperatorCraftCategory[];
}

interface OperatorCraftItemsResponse {
  success: true;
  items: OperatorCraftItem[];
}

interface OperatorCraftBudgetResponse {
  success: true;
  budget: OperatorCraftBudget;
}

interface OperatorCraftVideosResponse {
  success: true;
  videos: OperatorCraftVideo[];
}

interface OperatorDialectsResponse {
  success: true;
  dialects: OperatorDialect[];
}

interface OperatorDialectPhrasesResponse {
  success: true;
  phrases: OperatorDialectPhrase[];
}

interface OperatorDialectQuestionsResponse {
  success: true;
  questions: OperatorDialectQuestion[];
}

export async function getOperatorFarmingProducts(): Promise<
  OperatorFarmingProduct[]
> {
  const response = await get<OperatorProductsResponse>(
    "/api/operator/farming/products",
  );
  return response.products;
}

export function createOperatorFarmingProduct(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>(
    "/api/operator/farming/products",
    payload,
  );
}

export function updateOperatorFarmingProduct(
  productId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/farming/products/${encodeURIComponent(productId)}`,
    payload,
  );
}

export function deleteOperatorFarmingProduct(
  productId: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/farming/products/${encodeURIComponent(productId)}`,
  );
}

export async function getOperatorPhenophases(
  productId?: string,
): Promise<OperatorPhenophase[]> {
  const query = productId
    ? `?product_id=${encodeURIComponent(productId)}`
    : "";
  const response = await get<OperatorPhenophasesResponse>(
    `/api/operator/farming/phenophases${query}`,
  );
  return response.phenophases;
}

export function createOperatorPhenophase(
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    "/api/operator/farming/phenophases",
    payload,
  );
}

export function updateOperatorPhenophase(
  phaseId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/farming/phenophases/${phaseId}`,
    payload,
  );
}

export function deleteOperatorPhenophase(
  phaseId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/farming/phenophases/${phaseId}`,
  );
}

export async function getOperatorFarmingSources(): Promise<
  OperatorFarmingSource[]
> {
  const response = await get<OperatorFarmingSourcesResponse>(
    "/api/operator/farming/sources",
  );
  return response.sources;
}

export function createOperatorFarmingSource(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>(
    "/api/operator/farming/sources",
    payload,
  );
}

export function updateOperatorFarmingSource(
  key: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/farming/sources/${encodeURIComponent(key)}`,
    payload,
  );
}

export function deleteOperatorFarmingSource(
  key: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/farming/sources/${encodeURIComponent(key)}`,
  );
}

export async function getOperatorFarmingCategories(): Promise<
  OperatorFarmingCategory[]
> {
  const response = await get<OperatorFarmingCategoriesResponse>(
    "/api/operator/farming/categories",
  );
  return response.categories;
}

export function createOperatorFarmingCategory(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>(
    "/api/operator/farming/categories",
    payload,
  );
}

export function updateOperatorFarmingCategory(
  key: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/farming/categories/${encodeURIComponent(key)}`,
    payload,
  );
}

export function deleteOperatorFarmingCategory(
  key: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/farming/categories/${encodeURIComponent(key)}`,
  );
}

export async function getOperatorFarmingTasks(options?: {
  productId?: string;
  month?: number | "";
  overdue?: boolean;
}): Promise<OperatorFarmingTask[]> {
  const params = new URLSearchParams();
  if (options?.productId) params.set("product_id", options.productId);
  if (options?.month) params.set("month", String(options.month));
  if (options?.overdue) params.set("overdue", "1");
  const query = params.size ? `?${params.toString()}` : "";
  const response = await get<OperatorFarmingTasksResponse>(
    `/api/operator/farming/tasks${query}`,
  );
  return response.tasks;
}

export function createOperatorFarmingTask(
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    "/api/operator/farming/tasks",
    payload,
  );
}

export function updateOperatorFarmingTask(
  taskId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/farming/tasks/${taskId}`,
    payload,
  );
}

export function deleteOperatorFarmingTask(
  taskId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/farming/tasks/${taskId}`,
  );
}

export function verifyOperatorFarmingTask(
  taskId: number,
): Promise<OperatorResult<boolean>> {
  return post<OperatorResult<boolean>>(
    `/api/operator/farming/tasks/${taskId}/verify`,
    {},
  );
}

export async function getOperatorPestCrops(): Promise<OperatorPestCrop[]> {
  const response = await get<OperatorPestCropsResponse>(
    "/api/operator/pest/crops",
  );
  return response.crops;
}

export function createOperatorPestCrop(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>("/api/operator/pest/crops", payload);
}

export function updateOperatorPestCrop(
  cropId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/pest/crops/${encodeURIComponent(cropId)}`,
    payload,
  );
}

export function deleteOperatorPestCrop(
  cropId: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/pest/crops/${encodeURIComponent(cropId)}`,
  );
}

export async function getOperatorPestSources(): Promise<
  OperatorPestSource[]
> {
  const response = await get<OperatorPestSourcesResponse>(
    "/api/operator/pest/sources",
  );
  return response.sources;
}

export function createOperatorPestSource(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>(
    "/api/operator/pest/sources",
    payload,
  );
}

export function updateOperatorPestSource(
  key: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/pest/sources/${encodeURIComponent(key)}`,
    payload,
  );
}

export function deleteOperatorPestSource(
  key: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/pest/sources/${encodeURIComponent(key)}`,
  );
}

export async function getOperatorPestEntries(options?: {
  cropId?: string;
  overdue?: boolean;
}): Promise<OperatorPestEntrySummary[]> {
  const params = new URLSearchParams();
  if (options?.cropId) params.set("crop_id", options.cropId);
  if (options?.overdue) params.set("overdue", "1");
  const query = params.size ? `?${params.toString()}` : "";
  const response = await get<OperatorPestEntriesResponse>(
    `/api/operator/pest/entries${query}`,
  );
  return response.entries;
}

export async function getOperatorPestEntry(
  entryId: string,
): Promise<OperatorPestEntryDetail> {
  const response = await get<OperatorPestEntryResponse>(
    `/api/operator/pest/entries/${encodeURIComponent(entryId)}`,
  );
  return response.entry;
}

export function createOperatorPestEntry(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>(
    "/api/operator/pest/entries",
    payload,
  );
}

export function updateOperatorPestEntry(
  entryId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/pest/entries/${encodeURIComponent(entryId)}`,
    payload,
  );
}

export function deleteOperatorPestEntry(
  entryId: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/pest/entries/${encodeURIComponent(entryId)}`,
  );
}

export function verifyOperatorPestEntry(
  entryId: string,
): Promise<OperatorResult<boolean>> {
  return post<OperatorResult<boolean>>(
    `/api/operator/pest/entries/${encodeURIComponent(entryId)}/verify`,
    {},
  );
}

export function setOperatorPestImage(
  entryId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<null>> {
  return put<OperatorResult<null>>(
    `/api/operator/pest/entries/${encodeURIComponent(entryId)}/image`,
    payload,
  );
}

export function deleteOperatorPestImage(
  entryId: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/pest/entries/${encodeURIComponent(entryId)}/image`,
  );
}

export interface OperatorRecruitmentCatalog {
  recruitments: OperatorRecruitment[];
  categories: string[];
}

export async function getOperatorRecruitments(): Promise<
  OperatorRecruitmentCatalog
> {
  const response = await get<OperatorRecruitmentsResponse>(
    "/api/operator/recruitments",
  );
  return {
    recruitments: response.recruitments,
    categories: response.categories,
  };
}

export function createOperatorRecruitment(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>(
    "/api/operator/recruitments",
    payload,
  );
}

export function updateOperatorRecruitment(
  key: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/recruitments/${encodeURIComponent(key)}`,
    payload,
  );
}

export function deleteOperatorRecruitment(
  key: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/recruitments/${encodeURIComponent(key)}`,
  );
}

export async function getOperatorRecruitmentSources(
  key: string,
): Promise<OperatorRecruitmentSource[]> {
  const response = await get<OperatorRecruitmentSourcesResponse>(
    `/api/operator/recruitments/${encodeURIComponent(key)}/sources`,
  );
  return response.sources;
}

export function createOperatorRecruitmentSource(
  key: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/recruitments/${encodeURIComponent(key)}/sources`,
    payload,
  );
}

export function updateOperatorRecruitmentSource(
  sourceId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/recruitments/sources/${sourceId}`,
    payload,
  );
}

export function deleteOperatorRecruitmentSource(
  sourceId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/recruitments/sources/${sourceId}`,
  );
}

export async function getOperatorCases(): Promise<OperatorCaseSummary[]> {
  const response = await get<OperatorCasesResponse>("/api/operator/cases");
  return response.cases;
}

export function createOperatorCase(
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>("/api/operator/cases", payload);
}

export function updateOperatorCase(
  caseId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/cases/${caseId}`,
    payload,
  );
}

export function deleteOperatorCase(
  caseId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(`/api/operator/cases/${caseId}`);
}

export async function getOperatorCaseStats(
  caseId: number,
): Promise<OperatorCaseStat[]> {
  const response = await get<OperatorCaseStatsResponse>(
    `/api/operator/cases/${caseId}/stats`,
  );
  return response.stats;
}

export function createOperatorCaseStat(
  caseId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/cases/${caseId}/stats`,
    payload,
  );
}

export function updateOperatorCaseStat(
  statId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/cases/stats/${statId}`,
    payload,
  );
}

export function deleteOperatorCaseStat(
  statId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/cases/stats/${statId}`,
  );
}

export async function getOperatorCaseMilestones(
  caseId: number,
): Promise<OperatorCaseMilestone[]> {
  const response = await get<OperatorCaseMilestonesResponse>(
    `/api/operator/cases/${caseId}/milestones`,
  );
  return response.milestones;
}

export function createOperatorCaseMilestone(
  caseId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/cases/${caseId}/milestones`,
    payload,
  );
}

export function updateOperatorCaseMilestone(
  milestoneId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/cases/milestones/${milestoneId}`,
    payload,
  );
}

export function deleteOperatorCaseMilestone(
  milestoneId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/cases/milestones/${milestoneId}`,
  );
}

export async function getOperatorCaseSources(
  caseId: number,
): Promise<OperatorCaseSource[]> {
  const response = await get<OperatorCaseSourcesResponse>(
    `/api/operator/cases/${caseId}/sources`,
  );
  return response.sources;
}

export function createOperatorCaseSource(
  caseId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/cases/${caseId}/sources`,
    payload,
  );
}

export function updateOperatorCaseSource(
  sourceId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/cases/sources/${sourceId}`,
    payload,
  );
}

export function deleteOperatorCaseSource(
  sourceId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/cases/sources/${sourceId}`,
  );
}

export async function getOperatorCaseLessons(
  caseId: number,
): Promise<OperatorCaseLesson[]> {
  const response = await get<OperatorCaseLessonsResponse>(
    `/api/operator/cases/${caseId}/lessons`,
  );
  return response.lessons;
}

export function createOperatorCaseLesson(
  caseId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/cases/${caseId}/lessons`,
    payload,
  );
}

export function updateOperatorCaseLesson(
  lessonId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/cases/lessons/${lessonId}`,
    payload,
  );
}

export function deleteOperatorCaseLesson(
  lessonId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/cases/lessons/${lessonId}`,
  );
}

export async function getOperatorCrafts(): Promise<OperatorCraftSummary[]> {
  const response = await get<OperatorCraftsResponse>("/api/operator/crafts");
  return response.crafts;
}

export function createOperatorCraft(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>("/api/operator/crafts", payload);
}

export function updateOperatorCraft(
  craftId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}`,
    payload,
  );
}

export function deleteOperatorCraft(
  craftId: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}`,
  );
}

export async function getOperatorCraftSteps(
  craftId: string,
): Promise<OperatorCraftStep[]> {
  const response = await get<OperatorCraftStepsResponse>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/steps`,
  );
  return response.steps;
}

export function createOperatorCraftStep(
  craftId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/steps`,
    payload,
  );
}

export function updateOperatorCraftStep(
  stepId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/crafts/steps/${stepId}`,
    payload,
  );
}

export function deleteOperatorCraftStep(
  stepId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/crafts/steps/${stepId}`,
  );
}

export async function getOperatorCraftCategories(
  craftId: string,
): Promise<OperatorCraftCategory[]> {
  const response = await get<OperatorCraftCategoriesResponse>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/purchase-categories`,
  );
  return response.categories;
}

export function createOperatorCraftCategory(
  craftId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<{ craft_id: string; key: string }>> {
  return post<OperatorResult<{ craft_id: string; key: string }>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/purchase-categories`,
    payload,
  );
}

export function updateOperatorCraftCategory(
  craftId: string,
  categoryKey: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/purchase-categories/${encodeURIComponent(categoryKey)}`,
    payload,
  );
}

export function deleteOperatorCraftCategory(
  craftId: string,
  categoryKey: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/purchase-categories/${encodeURIComponent(categoryKey)}`,
  );
}

export async function getOperatorCraftItems(
  craftId: string,
  categoryKey?: string,
): Promise<OperatorCraftItem[]> {
  const query = categoryKey
    ? `?category_key=${encodeURIComponent(categoryKey)}`
    : "";
  const response = await get<OperatorCraftItemsResponse>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/purchase-items${query}`,
  );
  return response.items;
}

export function createOperatorCraftItem(
  craftId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/purchase-items`,
    payload,
  );
}

export function updateOperatorCraftItem(
  itemId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/crafts/purchase-items/${itemId}`,
    payload,
  );
}

export function deleteOperatorCraftItem(
  itemId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/crafts/purchase-items/${itemId}`,
  );
}

export async function getOperatorCraftBudget(
  craftId: string,
): Promise<OperatorCraftBudget | null> {
  try {
    const response = await get<OperatorCraftBudgetResponse>(
      `/api/operator/crafts/${encodeURIComponent(craftId)}/budget`,
    );
    return response.budget;
  } catch (error) {
    if (isStatus(error, 404)) return null;
    throw error;
  }
}

export function updateOperatorCraftBudget(
  craftId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return put<OperatorResult<string>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/budget`,
    payload,
  );
}

export async function getOperatorCraftVideos(
  craftId: string,
): Promise<OperatorCraftVideo[]> {
  const response = await get<OperatorCraftVideosResponse>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/videos`,
  );
  return response.videos;
}

export function createOperatorCraftVideo(
  craftId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/crafts/${encodeURIComponent(craftId)}/videos`,
    payload,
  );
}

export function updateOperatorCraftVideo(
  videoId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/crafts/videos/${videoId}`,
    payload,
  );
}

export function deleteOperatorCraftVideo(
  videoId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/crafts/videos/${videoId}`,
  );
}

export async function getOperatorDialects(): Promise<OperatorDialect[]> {
  const response = await get<OperatorDialectsResponse>(
    "/api/operator/dialects",
  );
  return response.dialects;
}

export function createOperatorDialect(
  payload: Record<string, unknown>,
): Promise<OperatorResult<string>> {
  return post<OperatorResult<string>>("/api/operator/dialects", payload);
}

export function updateOperatorDialect(
  dialectId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/dialects/${encodeURIComponent(dialectId)}`,
    payload,
  );
}

export function deleteOperatorDialect(
  dialectId: string,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/dialects/${encodeURIComponent(dialectId)}`,
  );
}

export async function getOperatorDialectPhrases(
  dialectId: string,
): Promise<OperatorDialectPhrase[]> {
  const response = await get<OperatorDialectPhrasesResponse>(
    `/api/operator/dialects/${encodeURIComponent(dialectId)}/phrases`,
  );
  return response.phrases;
}

export function createOperatorDialectPhrase(
  dialectId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/dialects/${encodeURIComponent(dialectId)}/phrases`,
    payload,
  );
}

export function updateOperatorDialectPhrase(
  phraseId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/dialects/phrases/${phraseId}`,
    payload,
  );
}

export function deleteOperatorDialectPhrase(
  phraseId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/dialects/phrases/${phraseId}`,
  );
}

export async function getOperatorDialectQuestions(
  dialectId: string,
): Promise<OperatorDialectQuestion[]> {
  const response = await get<OperatorDialectQuestionsResponse>(
    `/api/operator/dialects/${encodeURIComponent(dialectId)}/quick-questions`,
  );
  return response.questions;
}

export function createOperatorDialectQuestion(
  dialectId: string,
  payload: Record<string, unknown>,
): Promise<OperatorResult<number>> {
  return post<OperatorResult<number>>(
    `/api/operator/dialects/${encodeURIComponent(dialectId)}/quick-questions`,
    payload,
  );
}

export function updateOperatorDialectQuestion(
  questionId: number,
  payload: Record<string, unknown>,
): Promise<OperatorResult<boolean>> {
  return put<OperatorResult<boolean>>(
    `/api/operator/dialects/quick-questions/${questionId}`,
    payload,
  );
}

export function deleteOperatorDialectQuestion(
  questionId: number,
): Promise<OperatorResult<boolean>> {
  return del<OperatorResult<boolean>>(
    `/api/operator/dialects/quick-questions/${questionId}`,
  );
}

function isStatus(error: unknown, status: number): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    error.status === status
  );
}
