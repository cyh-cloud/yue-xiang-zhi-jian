import { describe, expect, it } from "vitest";

import {
  MODEL_3D_EXTENSIONS,
  toUploadError,
  validateModel3dFile,
} from "./upload";
import { ApiError } from "./client";

function modelFile(name: string, size: number): File {
  return new File([new Uint8Array(size)], name, {
    type: "application/octet-stream",
  });
}

describe("validateModel3dFile", () => {
  it("accepts every supported model extension", () => {
    for (const extension of MODEL_3D_EXTENSIONS) {
      expect(validateModel3dFile(modelFile(`model.${extension}`, 4))).toBeNull();
    }
  });

  it("rejects a missing or byte-empty file as file_empty", () => {
    expect(validateModel3dFile(null)?.code).toBe("file_empty");
    expect(validateModel3dFile(modelFile("empty.glb", 0))?.code).toBe("file_empty");
  });

  it("rejects unsupported extensions before uploading", () => {
    expect(validateModel3dFile(modelFile("installer.exe", 4))).toMatchObject({
      code: "unsupported_format",
    });
  });

  it("rejects files above the shared 50MB limit", () => {
    expect(validateModel3dFile(modelFile("huge.glb", 50 * 1024 * 1024 + 1))).toMatchObject({
      code: "file_too_large",
      message: expect.stringContaining("50MB"),
    });
  });
});

describe("toUploadError", () => {
  it("maps 413 and connection failures to actionable upload failures", () => {
    expect(toUploadError(new ApiError({ status: 413, code: null, message: "" }))).toMatchObject({
      status: 413,
      code: "file_too_large",
    });
    expect(toUploadError(new ApiError({ status: 0, code: null, message: "" }))).toMatchObject({
      status: 0,
      code: "network_error",
    });
  });

  it("preserves backend rejection codes", () => {
    expect(
      toUploadError(
        new ApiError({ status: 400, code: "empty_file", message: "文件为空" }),
      ),
    ).toMatchObject({
      status: 400,
      code: "file_empty",
      message: "文件为空",
    });
  });
});
