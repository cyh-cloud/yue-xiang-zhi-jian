import { ApiError, postForm } from "./client";
import {
  MAX_UPLOAD_BYTES,
  MAX_UPLOAD_MEGABYTES,
  MODEL_3D_EXTENSIONS,
} from "./uploadLimits";

export { MODEL_3D_EXTENSIONS };

export type UploadFailureCode =
  | "file_empty"
  | "unsupported_format"
  | "file_too_large"
  | "network_error"
  | "backend_rejected";

export interface UploadFailure {
  code: UploadFailureCode;
  message: string;
}

export interface Model3dUploadResponse {
  success: true;
  id: number;
  message: string;
}

export interface Model3dUploadInput {
  file: File;
  title?: string;
  description?: string;
  craftType?: string;
}

export function validateModel3dFile(file: File | null | undefined): UploadFailure | null {
  if (!file || !file.name.trim() || file.size === 0) {
    return {
      code: "file_empty",
      message: "请选择一个非空的 3D 模型文件。",
    };
  }

  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!MODEL_3D_EXTENSIONS.includes(extension as (typeof MODEL_3D_EXTENSIONS)[number])) {
    return {
      code: "unsupported_format",
      message: `不支持该文件格式。请选择 ${MODEL_3D_EXTENSIONS.join("/")} 文件。`,
    };
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      code: "file_too_large",
      message: `文件过大，模型文件不能超过 ${MAX_UPLOAD_MEGABYTES}MB。`,
    };
  }

  return null;
}

export async function uploadModel3d(
  input: Model3dUploadInput,
): Promise<Model3dUploadResponse> {
  const failure = validateModel3dFile(input.file);
  if (failure) throw new ApiError({ status: 0, code: failure.code, message: failure.message });

  const form = new FormData();
  // Keep this test visible at the call site: no JSON Content-Type is set.
  form.append("file", input.file);
  form.append("title", input.title?.trim() || input.file.name);
  form.append("description", input.description?.trim() ?? "");
  form.append("craft_type", input.craftType ?? "");

  try {
    return await postForm<Model3dUploadResponse>("/api/teacher/models-3d", form);
  } catch (error) {
    throw toUploadError(error);
  }
}

export function toUploadError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    if (error.code === "empty_file") {
      return new ApiError({
        status: error.status,
        code: "file_empty",
        message: error.message || "请选择一个非空的 3D 模型文件。",
      });
    }
    if (error.code === "unsupported_format") {
      return new ApiError({
        status: error.status,
        code: "unsupported_format",
        message: error.message || "不支持该文件格式。",
      });
    }
    if (error.status === 413) {
      return new ApiError({
        status: 413,
        code: "file_too_large",
        message: `文件过大，模型文件不能超过 ${MAX_UPLOAD_MEGABYTES}MB。`,
      });
    }
    if (error.status === 0) {
      return new ApiError({
        status: 0,
        code: "network_error",
        message: "无法连接上传服务，请检查网络后重试。",
      });
    }
    return new ApiError({
      status: error.status,
      code: error.code || "backend_rejected",
      message: error.message || "服务器拒绝了这次上传，请检查文件后重试。",
    });
  }

  return new ApiError({
    status: 0,
    code: "network_error",
    message: "无法连接上传服务，请检查网络后重试。",
  });
}
