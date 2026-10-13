export const documentationUrls = {
  public:
    process.env.NEXT_PUBLIC_ONESA_DOCUMENTATION_URL ||
    (process.env.NODE_ENV === "production" ? "https://docs.onesa.eu" : "http://localhost:3200"),
  internal:
    process.env.NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL ||
    (process.env.NODE_ENV === "production" ? "" : "http://localhost:3201"),
};
export const documentationRoutes = {
  chat: "/docs/public/applications#chat",
  knowledge: "/docs/public/applications#knowledge",
  agents: "/docs/public/applications#agents",
  travel: "/docs/public/applications#travel",
  model: "/docs/public/models",
  api: "/api-explorer",
};
