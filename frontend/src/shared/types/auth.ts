export interface CurrentUser {
  id: number;
  username: string;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginPayload {
  usernameOrEmail: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: CurrentUser;
}
