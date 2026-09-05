export const MIN_CHAT_HEIGHT = 200;
export const DEFAULT_CHAT_HEIGHT = 320;

export function getMaxChatHeight() {
  return window.innerHeight * 0.7;
}

export function clampChatHeight(height: number) {
  return Math.min(getMaxChatHeight(), Math.max(MIN_CHAT_HEIGHT, height));
}
