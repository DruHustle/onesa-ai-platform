import type { Metadata } from "next";
export const metadata: Metadata = { title: "Invitation" };
export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
