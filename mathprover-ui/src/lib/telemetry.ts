import pino from "pino";

const isDev = typeof process !== "undefined" && process.env?.NODE_ENV !== "production";

export const log = pino({
  level: isDev ? "debug" : "info",
  ...(isDev
    ? {
        transport: {
          target: "pino-pretty",
          options: { colorize: true, translateTime: "HH:MM:ss" },
        },
      }
    : {}),
});
