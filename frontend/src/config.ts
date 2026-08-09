/**
 * 前端路由与资源 base。
 * Vite BASE_URL 始终以 / 结尾：本地开发为 "/"，生产构建为 "/projects/wordnest/"。
 * API 仍走绝对路径 /api/wordnest，不随页面子路径变化。
 */
export const APP_BASENAME = import.meta.env.BASE_URL.replace(/\/$/, "");
