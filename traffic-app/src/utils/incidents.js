import { formatDateKey, t } from "./i18n.js";
import { buildIncidentImagePath, formatTimestamp } from "./helpers.js";

export function fuzzyMatch(query, text) {
  if (!query) return true;
  if (!text) return false;

  const normalizedQuery = query.toLowerCase();
  const normalizedText = text.toLowerCase();
  if (normalizedText.includes(normalizedQuery)) return true;

  return normalizedQuery
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => normalizedText.includes(word));
}

/**
 * Convert an API incident into the UI's post shape while preserving local UI state.
 *
 * @param {Record<string, any>} incident
 * @param {Record<string, any>} [existingPost={}]
 */
export function buildPostFromIncident(incident, existingPost = {}) {
  const timestamp = incident.timestamp || existingPost.timestamp || "";
  const date = formatDateKey(timestamp);

  return {
    id: incident.incident_no ?? existingPost.id,
    compositeId: `${incident.incident_no}-${date}`,
    details: Array.isArray(incident.Details) ? incident.Details : [],
    timestamp,
    time: formatTimestamp(timestamp),
    description: incident.description || t("fallback.descriptionUnavailable"),
    showFullDescription: existingPost.showFullDescription ?? false,
    location: incident.location || t("fallback.unknownLocation"),
    neighborhood: incident.neighborhood || "",
    latitude: incident.latitude ?? null,
    longitude: incident.longitude ?? null,
    image: buildIncidentImagePath(incident.map_filename),
    likes: typeof incident.likes === "number" ? incident.likes : existingPost.likes ?? 0,
    comments: Array.isArray(incident.comments)
      ? incident.comments
      : existingPost.comments ?? [],
    newComment: existingPost.newComment ?? "",
    showComments: existingPost.showComments ?? false,
    type: incident.type || t("fallback.trafficIncident"),
    likeError: existingPost.likeError ?? "",
    commentError: existingPost.commentError ?? "",
    likeErrorAnimation: existingPost.likeErrorAnimation ?? false,
    active: Boolean(incident.active),
    liking: existingPost.liking ?? false,
    severity: incident.severity ?? null,
    likedByUser:
      typeof incident.liked_by_user === "boolean"
        ? incident.liked_by_user
        : existingPost.likedByUser ?? false,
  };
}
