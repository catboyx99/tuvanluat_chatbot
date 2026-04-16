import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

/* Load Google-style fonts (Geist Sans cho giao diện luật chuyên nghiệp) */
const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

/* SEO Metadata - Tiêu đề và mô tả cho trang web */
export const metadata: Metadata = {
  title: "AI tư vấn pháp chế",
  description: "Chatbot tư vấn pháp luật Việt Nam sử dụng trí tuệ nhân tạo, hỗ trợ tra cứu luật, nghị định, thông tư.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
