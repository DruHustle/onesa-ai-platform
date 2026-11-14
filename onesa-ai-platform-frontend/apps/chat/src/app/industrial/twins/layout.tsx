import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Digital Twins · Industrial AI",
  robots: { index: false, follow: false },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
