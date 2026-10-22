export type Role =
  | "student"
  | "teacher"
  | "enterprise"
  | "government"
  | "operator"
  | "super_admin";

export interface User {
  id: string;
  name: string;
  role: Role;
  email: string;
  phone: string;
  avatar_url: string;
  company_name: string;
  region: string;
  status: string;
}

export interface AuthResponse {
  success: true;
  session_id: string;
  user: User;
  capabilities: string[];
}

export interface RegisterPayload {
  username: string;
  password: string;
  name: string;
  role: "student" | "teacher" | "enterprise";
  email?: string;
  phone?: string;
  company_name?: string;
  region?: string;
}

export interface VerifyResponse {
  success: true;
  user: User;
  capabilities: string[];
}

export interface CapabilitiesResponse {
  success: true;
  role: Role | "";
  capabilities: string[];
}

export interface LogoutResponse {
  success: true;
  message: string;
}
