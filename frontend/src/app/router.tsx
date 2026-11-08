import { QueryClient } from "@tanstack/react-query";
import { createBrowserRouter } from "react-router-dom";
import { Layout } from "../app/Layout";
import { Dashboard } from "../features/dashboard/Dashboard";
import { Stories } from "../features/stories/StoriesPage";
import { History } from "../features/jobs/HistoryPage";
import { Connection } from "../features/connection/ConnectionPage";
import { JobDetail } from "../features/jobs/JobDetail";
import { StoryDetail } from "../features/stories/StoryDetail";

export const client = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false },
    mutations: { retry: false },
  },
});
export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "stories", element: <Stories /> },
      { path: "stories/:id", element: <StoryDetail /> },
      { path: "history", element: <History /> },
      { path: "jobs/:id", element: <JobDetail /> },
      { path: "connection", element: <Connection /> },
      {
        path: "*",
        element: (
          <div className="empty">
            <h1>Stránka sa nenašla</h1>
            <a href="/">Späť na prehľad</a>
          </div>
        ),
      },
    ],
  },
]);
