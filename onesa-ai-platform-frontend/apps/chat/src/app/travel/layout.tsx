import type { Metadata } from "next";
export const metadata: Metadata = { title: "Travel" };
export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
