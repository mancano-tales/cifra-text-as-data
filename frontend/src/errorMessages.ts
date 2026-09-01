import type { TFunction } from "i18next";
import { ApiError } from "./api";

/**
 * Backend error details are plain English strings interpolated with
 * identifiers (corpus names, ids) — not safe to translate word-for-word.
 * Show a localized generic message keyed off the HTTP status, with the raw
 * detail kept alongside as untranslated technical context.
 */
export function describeApiError(err: unknown, t: TFunction): { message: string; detail?: string } {
  if (err instanceof ApiError) {
    const key =
      err.status === 404
        ? "errors.notFound"
        : err.status === 409
          ? "errors.conflict"
          : err.status === 422
            ? "errors.validation"
            : err.status === 400
              ? "errors.badRequest"
              : err.status >= 500
                ? "errors.server"
                : "errors.unknown";
    return { message: t(key), detail: err.detail };
  }
  return { message: err instanceof Error ? err.message : t("errors.unknown") };
}
